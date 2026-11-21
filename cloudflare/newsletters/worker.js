// The newsletters Worker (issue 152). Receives mail sent to newsletters@feeds.opengnss.org and serves
// https://feeds.opengnss.org/substack/<publication>/feed, which the archive job reads like any other feed.
// Only mail that Substack signed (DKIM) is kept. The raw email stays private in KV; the feed carries only the title,
// the post's public link, the date and a short excerpt.
// It also keeps mail to the contact address (CONTACT_TO, contact@opengnss.org) privately, for the team to read in the
// console through GET /contact with the CONTACT_READ_TOKEN secret. That mail is never published and never bounced.
// The dashboard's contact form adds to the same inbox through POST /contact with the CONTACT_WRITE_TOKEN secret.
// Messages form threads; the console replies through POST /contact/reply (the read token), sent with the EMAIL binding
// (Cloudflare Email Service) from the contact address, and only ever to the thread's correspondent.
// Attachments are kept beside their message and stay unreadable until a GitHub job (.github/workflows/contact-scan.yml)
// has scanned them with ClamAV through the /contact/attachments routes (the CONTACT_SCAN_TOKEN secret).
//
// KV writes (1000 a day on the free plan, shared with the newsletters), per contact message:
//   1 for the message, + 1 per attachment kept (at most 3), + 1 per attachment when its scan result arrives;
//   a reply sent from the console is 1. So a message with 3 files costs 7 writes in all, one without costs 1.
//   An attachment's scan state lives in its own key's metadata, so a verdict rewrites only that key, never the message.
import PostalMime from "postal-mime";
import {
  CONTACT_DAILY_MESSAGES, CONTACT_READ_ITEMS, CONTACT_TO, FEED_ITEMS, asMessageId, authorized, contactRecord, excerpt, formAttachments, formMessage,
  fromSubstack, isContact, newestFirst, postLink, publicationOf, receiverResults, replyTo, rss, sameTokens, scanResult,
  sortAttachments, threadOf,
} from "./lib.js";

const CONTACT = "contact:";        // contact:<time>:<id>, one message
const FILE = "contact-file:";      // contact-file:<id>, one attachment's bytes; metadata {scan, signature, name, type, size}
const CONTACT_BODY_CHARACTERS = 8 * 1024 * 1024;   // a form message with 5 MB of files is about 6.7 MB as base64 JSON
const HEADER_IDS = 2000;           // characters of In-Reply-To or References kept, for threading

// Every key under a prefix, with its metadata.
async function keys(env, prefix) {
  const found = [];
  let cursor;
  do {   // ponytail: lists every key under the prefix each read; keep an index if that grows slow
    const page = await env.NEWSLETTERS.list({ prefix, cursor });
    found.push(...page.keys);
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return found;
}

// The newest values under a prefix, newest first.
async function newest(env, prefix, limit) {
  const names = newestFirst((await keys(env, prefix)).map((k) => k.name), limit);
  return (await Promise.all(names.map((name) => env.NEWSLETTERS.get(name, "json")))).filter(Boolean);
}

// The newest contact messages, newest first, each with its id and every attachment's scan state. A message kept before
// threads existed is a thread of its own, from a correspondent.
// ponytail: only the newest 200 messages are threaded or replied to; an index key per Message-ID if older ones matter
async function inbox(env) {
  const [messages, files] = await Promise.all([keys(env, CONTACT), keys(env, FILE)]);
  const scans = new Map(files.map((k) => [k.name.slice(FILE.length), k.metadata || {}]));
  const names = newestFirst(messages.map((k) => k.name), CONTACT_READ_ITEMS);
  const records = await Promise.all(names.map(async (name) => {
    const record = await env.NEWSLETTERS.get(name, "json");
    if (!record) return null;
    const id = name.slice(CONTACT.length);
    const attachments = (record.attachments || []).map((a) => (a.id
      ? { ...a, scan: scans.get(a.id)?.scan || "missing", signature: scans.get(a.id)?.signature || "" } : a));
    return { ...record, id, thread: record.thread || id, direction: record.direction || "in", attachments };
  }));
  return records.filter(Boolean);
}

// Each file under its own key, waiting to be scanned; returns what the message records of each.
const keepFiles = (env, files) => Promise.all(files.map(async ({ name, type, size, content }) => {
  const id = crypto.randomUUID();
  await env.NEWSLETTERS.put(`${FILE}${id}`, content, { metadata: { scan: "pending", name, type, size } });
  return { id, name, type, size };
}));

// One message into the contact inbox, under the time it arrived.
// Today's count of messages taken in, so a flood (or a leaked write token) cannot spend the newsletters' KV writes.
// ponytail: KV is eventually consistent, so a burst can pass the cap by a few; a Durable Object counter if that matters.
const countKey = () => `contact-count:${new Date().toISOString().slice(0, 10)}`;
const roomToday = async (env) => (Number(await env.NEWSLETTERS.get(countKey())) || 0) < CONTACT_DAILY_MESSAGES;
async function countToday(env) {   // after the message is kept: a failed count never turns a kept message into an error
  const key = countKey();
  try {
    await env.NEWSLETTERS.put(key, String((Number(await env.NEWSLETTERS.get(key)) || 0) + 1), { expirationTtl: 2 * 86400 });
  } catch { /* the cap undercounts by one; the message itself is kept */ }
}

const keepContact = (env, record) =>
  env.NEWSLETTERS.put(`${CONTACT}${record.at}:${crypto.randomUUID().slice(0, 8)}`, JSON.stringify(record));

const headerIds = (value) => String(value || "").slice(0, HEADER_IDS);
const notAllowed = () => new Response("Not allowed.\n", { status: 401, headers: { "www-authenticate": "Bearer" } });
const refused = (status, problem) => Response.json({ ok: false, problem }, { status });
const NO_STORE = { "cache-control": "no-store" };

// The routes under /contact/attachments: the scan job lists, fetches and judges; the console fetches a clean file.
async function attachments(request, env, path) {
  const auth = request.headers.get("authorization");
  const scanner = authorized(auth, env.CONTACT_SCAN_TOKEN), reader = authorized(auth, env.CONTACT_READ_TOKEN);
  if (path === "/contact/attachments" && request.method === "GET") {
    if (!scanner) return notAllowed();
    const wanted = new URL(request.url).searchParams.get("scan");
    const files = (await keys(env, FILE)).map((k) => ({ id: k.name.slice(FILE.length), ...(k.metadata || {}) }));
    return Response.json(files.filter((f) => !wanted || f.scan === wanted), { headers: NO_STORE });
  }
  const found = path.match(/^\/contact\/attachments\/([0-9a-f-]{36})(\/scan)?$/);
  if (!found) return new Response("Not found.\n", { status: 404 });
  const key = `${FILE}${found[1]}`;
  if (found[2] && request.method === "POST") {
    if (!scanner) return notAllowed();
    const verdict = scanResult(await request.json().catch(() => null));
    if (verdict.problem) return refused(400, verdict.problem);
    const { value, metadata } = await env.NEWSLETTERS.getWithMetadata(key, "arrayBuffer");
    if (value === null) return refused(404, "no such attachment");
    if ((metadata?.scan || "pending") !== "pending") return refused(409, `already scanned: ${metadata.scan}`);   // a leaked scan token cannot remove a clean file
    if (verdict.result === "clean") await env.NEWSLETTERS.put(key, value, { metadata: { ...metadata, scan: "clean" } });
    else await env.NEWSLETTERS.put(key, "", { metadata: { ...metadata, scan: "infected", signature: verdict.signature } });   // bytes gone, record kept
    return Response.json({ ok: true, scan: verdict.result });
  }
  if (found[2] || request.method !== "GET") return new Response("Not found.\n", { status: 404 });
  if (!scanner && !reader) return notAllowed();
  const { value, metadata } = await env.NEWSLETTERS.getWithMetadata(key, "arrayBuffer");
  if (value === null) return refused(404, "no such attachment");
  const scan = metadata?.scan || "pending";
  // The scanner fetches a file only while it waits to be scanned; the console only once it is clean.
  const allowed = (scanner && scan === "pending") || (reader && scan === "clean");
  if (!allowed) return Response.json({ ok: false, scan }, { status: 409 });
  return new Response(value, {
    headers: {
      ...NO_STORE, "content-type": metadata?.type || "application/octet-stream", "x-content-type-options": "nosniff",
      "content-disposition": `attachment; filename*=UTF-8''${encodeURIComponent(metadata?.name || "attachment")}`,
    },
  });
}

// POST /contact/reply {thread, text}: a plain-text reply to the thread's correspondent, kept in the thread.
async function reply(request, env) {
  if (!authorized(request.headers.get("authorization"), env.CONTACT_READ_TOKEN)) return notAllowed();
  if (!env.EMAIL) return refused(503, "email sending is not set up: the Worker has no EMAIL binding");
  const body = await request.json().catch(() => null);
  const thread = body && typeof body.thread === "string" ? body.thread : "";
  const mail = replyTo(await inbox(env), thread, body && body.text);
  if (mail.problem) return refused(mail.status, mail.problem);
  const from = (env.CONTACT_TO || CONTACT_TO).trim().toLowerCase();
  let sent;
  try {
    sent = await env.EMAIL.send({ to: mail.to, from: { email: from, name: "OpenGNSS" }, subject: mail.subject, text: mail.text, headers: mail.headers });
  } catch (error) {
    return refused(502, `email not sent (${error.code || "error"}): ${error.message || "no reason given"}`);
  }
  // Email Service sets the Message-ID itself and returns it; kept so the correspondent's answer joins this thread.
  // Should the two ever differ, their answer still names their own first message in References, so it threads anyway.
  await keepContact(env, {
    thread, direction: "out", from, address: from, to: mail.to, subject: mail.subject, at: new Date().toISOString(), text: mail.text,
    message_id: asMessageId(sent && sent.messageId), in_reply_to: mail.headers["In-Reply-To"] || "", references: mail.headers.References || "",
  });
  return Response.json({ ok: true }, { status: 201 });
}

export default {
  async email(message, env) {
    const raw = await new Response(message.raw).arrayBuffer();
    const mail = await PostalMime.parse(raw);
    if (isContact(message.to, env.CONTACT_TO)) {   // the time it arrived, not the Date the sender wrote
      if (!(await roomToday(env))) {
        message.setReject("The OpenGNSS contact inbox is full for today. Please write again tomorrow.");
        return;
      }
      const { kept, noted } = sortAttachments((mail.attachments || []).map((a) => ({ name: a.filename, content: a.content })));
      await keepContact(env, {
        ...contactRecord(mail, message.from, new Date().toISOString()),
        thread: threadOf(mail, await inbox(env)) || crypto.randomUUID(), direction: "in",
        message_id: headerIds(mail.messageId), in_reply_to: headerIds(mail.inReplyTo), references: headerIds(mail.references),
        attachments: [...await keepFiles(env, kept), ...noted],
      });
      await countToday(env);
      return;
    }
    const headers = Object.fromEntries(mail.headers.map((h) => [h.key.toLowerCase(), h.value]));
    const at = new Date(mail.date || Date.now()).toISOString();
    const results = receiverResults(mail.headers);
    if (!fromSubstack(message.from, results)) {   // kept privately to check, never published and never bounced
      await env.NEWSLETTERS.put(`unverified:${at}`, JSON.stringify({ subject: mail.subject || "", from: message.from, results, at }));
      return;
    }
    const text = `${mail.text || ""}\n${mail.html || ""}`;
    const publication = publicationOf(headers, text);
    const link = publication && postLink(publication, text);
    if (!link) {   // a sign-in, welcome or confirmation email: never published; forwarded when a person is named
      await env.NEWSLETTERS.put(`notice:${at}`, JSON.stringify({ subject: mail.subject || "", from: message.from, at }));
      await env.NEWSLETTERS.put(`raw-notice:${at}`, raw);   // private, so a missed post can be recovered
      if (env.NOTICE_TO) await message.forward(env.NOTICE_TO);
      return;
    }
    const key = `${publication}:${at}:${crypto.randomUUID().slice(0, 8)}`;
    await env.NEWSLETTERS.put(`raw:${key}`, raw);
    await env.NEWSLETTERS.put(`post:${key}`, JSON.stringify({ title: mail.subject || link, link, date: at, excerpt: excerpt(mail.text) }));
  },

  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    const contactRoute = path === "/contact" || path.startsWith("/contact/");
    if (contactRoute && sameTokens(env)) {
      return new Response("Contact inbox closed: CONTACT_READ_TOKEN, CONTACT_WRITE_TOKEN and CONTACT_SCAN_TOKEN must all differ.\n", { status: 503 });
    }
    if (path === "/contact" && request.method === "GET") {   // the console: messages, newest first, each in its thread
      if (!authorized(request.headers.get("authorization"), env.CONTACT_READ_TOKEN)) return notAllowed();
      return Response.json(await inbox(env), { headers: NO_STORE });
    }
    if (path === "/contact" && request.method === "POST") {   // the dashboard's contact form
      if (!authorized(request.headers.get("authorization"), env.CONTACT_WRITE_TOKEN)) return notAllowed();
      if (!(await roomToday(env))) return refused(429, "the inbox takes no more messages today");
      const text = await request.text();
      if (text.length > CONTACT_BODY_CHARACTERS) return refused(413, "the message is too large");
      let body = null;
      try { body = JSON.parse(text); } catch { /* refused below */ }
      const form = formMessage(body);
      if (form.problem) return refused(400, form.problem);
      const files = formAttachments(body.attachments);
      if (files.problem) return refused(400, files.problem);
      const mail = { from: { address: form.from }, subject: form.subject, text: form.text };
      await keepContact(env, {
        ...contactRecord(mail, "", new Date().toISOString()), via: "form", thread: crypto.randomUUID(), direction: "in",
        attachments: await keepFiles(env, files.files),
      });
      await countToday(env);
      return Response.json({ ok: true }, { status: 201 });
    }
    if (path === "/contact/reply" && request.method === "POST") return reply(request, env);
    if (path === "/contact/attachments" || path.startsWith("/contact/attachments/")) return attachments(request, env, path);
    const found = path.match(/^\/substack\/([a-z0-9-]+)\/feed\/?$/);
    if (!found) return new Response("OpenGNSS feeds. See https://github.com/SumanthVarma798/GNSS-Constellation-Health-Monitoring-System\n");
    const posts = await newest(env, `post:${found[1]}:`, FEED_ITEMS);
    return new Response(rss(found[1], posts), { headers: { "content-type": "application/rss+xml; charset=utf-8" } });
  },
};

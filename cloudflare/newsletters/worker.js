// The newsletters Worker (issue 152). Receives mail sent to newsletters@feeds.opengnss.org and serves
// https://feeds.opengnss.org/substack/<publication>/feed, which the archive job reads like any other feed.
// Only mail that Substack signed (DKIM) is kept. The raw email stays private in KV; the feed carries only the title,
// the post's public link, the date and a short excerpt.
// It also keeps mail to the contact address (CONTACT_TO, contact@opengnss.org) privately, for the team to read in the
// console through GET /contact with the CONTACT_READ_TOKEN secret. That mail is never published and never bounced.
// The dashboard's contact form adds to the same inbox through POST /contact with the CONTACT_WRITE_TOKEN secret.
import PostalMime from "postal-mime";
import {
  CONTACT_READ_ITEMS, FEED_ITEMS, authorized, contactRecord, excerpt, formMessage, fromSubstack, isContact, newestFirst,
  postLink, publicationOf, receiverResults, rss, sameTokens,
} from "./lib.js";

// The newest values under a prefix, newest first.
async function newest(env, prefix, limit) {
  const keys = [];
  let cursor;
  do {   // ponytail: lists every key under the prefix each read; keep an index if that grows slow
    const page = await env.NEWSLETTERS.list({ prefix, cursor });
    keys.push(...page.keys.map((k) => k.name));
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return (await Promise.all(newestFirst(keys, limit).map((name) => env.NEWSLETTERS.get(name, "json")))).filter(Boolean);
}

// One message into the contact inbox, under the time it arrived.
const keepContact = (env, record) =>
  env.NEWSLETTERS.put(`contact:${record.at}:${crypto.randomUUID().slice(0, 8)}`, JSON.stringify(record));

export default {
  async email(message, env) {
    const raw = await new Response(message.raw).arrayBuffer();
    const mail = await PostalMime.parse(raw);
    if (isContact(message.to, env.CONTACT_TO)) {   // the time it arrived, not the Date the sender wrote
      await keepContact(env, contactRecord(mail, message.from, new Date().toISOString()));
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
    if (path === "/contact" && sameTokens(env)) {
      return new Response("Contact inbox closed: CONTACT_READ_TOKEN and CONTACT_WRITE_TOKEN must differ.\n", { status: 503 });
    }
    if (path === "/contact" && request.method === "GET") {
      if (!authorized(request.headers.get("authorization"), env.CONTACT_READ_TOKEN)) {
        return new Response("Not allowed.\n", { status: 401, headers: { "www-authenticate": "Bearer" } });
      }
      return Response.json(await newest(env, "contact:", CONTACT_READ_ITEMS), { headers: { "cache-control": "no-store" } });
    }
    if (path === "/contact" && request.method === "POST") {   // the dashboard's contact form
      if (!authorized(request.headers.get("authorization"), env.CONTACT_WRITE_TOKEN)) {
        return new Response("Not allowed.\n", { status: 401, headers: { "www-authenticate": "Bearer" } });
      }
      const form = formMessage(await request.json().catch(() => null));
      if (form.problem) return Response.json({ ok: false, problem: form.problem }, { status: 400 });
      const mail = { from: { address: form.from }, subject: form.subject, text: form.text };
      await keepContact(env, { ...contactRecord(mail, "", new Date().toISOString()), via: "form" });
      return Response.json({ ok: true }, { status: 201 });
    }
    const found = path.match(/^\/substack\/([a-z0-9-]+)\/feed\/?$/);
    if (!found) return new Response("OpenGNSS feeds. See https://github.com/SumanthVarma798/GNSS-Constellation-Health-Monitoring-System\n");
    const posts = await newest(env, `post:${found[1]}:`, FEED_ITEMS);
    return new Response(rss(found[1], posts), { headers: { "content-type": "application/rss+xml; charset=utf-8" } });
  },
};

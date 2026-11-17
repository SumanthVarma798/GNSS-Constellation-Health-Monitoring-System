// The Worker's contact routes end to end, with in-memory stand-ins for its KV store and its EMAIL binding.
// Run: node --test cloudflare/newsletters/
import assert from "node:assert/strict";
import { test } from "node:test";
import worker from "./worker.js";

function store() {
  const values = new Map(), metadata = new Map();
  return {
    values,
    async put(key, value, options) { values.set(key, value); metadata.set(key, options?.metadata ?? null); },
    async get(key, type) { const value = values.get(key); return value && type === "json" ? JSON.parse(value) : value ?? null; },
    async getWithMetadata(key) { return { value: values.has(key) ? values.get(key) : null, metadata: metadata.get(key) ?? null }; },
    async list({ prefix }) {
      const keys = [...values.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name, metadata: metadata.get(name) ?? undefined }));
      return { keys, list_complete: true };
    },
  };
}

function mailer() {
  const sent = [];
  return { sent, async send(message) { sent.push(message); return { messageId: `sent-${sent.length}@cf.example` }; } };
}

const TOKENS = { CONTACT_WRITE_TOKEN: "write-1", CONTACT_READ_TOKEN: "read-1", CONTACT_SCAN_TOKEN: "scan-1" };
const environment = (more = {}) => ({ NEWSLETTERS: store(), EMAIL: mailer(), ...TOKENS, ...more });

const call = (path, { method = "GET", body, token } = {}) => new Request(`https://feeds.opengnss.org${path}`, {
  method, body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
  headers: token ? { authorization: `Bearer ${token}` } : {},
});
const post = (body, token) => call("/contact", { method: "POST", body, token });
const read = (token) => call("/contact", { token });
const inbox = async (env) => (await worker.fetch(read("read-1"), env)).json();

// An email to the contact address, as the email() handler receives it.
function email(from, subject, extraHeaders = "", attachment = "") {
  const boundary = "b1";
  const body = attachment
    ? `Content-Type: multipart/mixed; boundary="${boundary}"\r\n\r\n--${boundary}\r\nContent-Type: text/plain\r\n\r\nSee attached\r\n`
      + `--${boundary}\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename="${attachment}"\r\n`
      + `Content-Transfer-Encoding: base64\r\n\r\n${btoa("%PDF-1.4 test")}\r\n--${boundary}--\r\n`
    : "Content-Type: text/plain\r\n\r\nHello team\r\n";
  const raw = `From: ${from}\r\nTo: contact@opengnss.org\r\nSubject: ${subject}\r\n${extraHeaders}${body}`;
  return { from, to: "contact@opengnss.org", raw: new Blob([raw]).stream() };
}

test("a form message with the write token is kept in the inbox, marked as from the form, and read back with the read token", async () => {
  const env = environment();
  assert.equal((await worker.fetch(post({ from: "a@example.org", text: "Hello" }), env)).status, 401);
  assert.equal((await worker.fetch(post({ from: "a@example.org", text: "Hello" }, "read-1"), env)).status, 401);
  const refused = await worker.fetch(post({ from: "not an address", text: "Hello" }, "write-1"), env);
  assert.equal(refused.status, 400);
  assert.equal((await refused.json()).problem, "from is not an email address");
  assert.equal((await worker.fetch(post("not json", "write-1"), env)).status, 400);
  assert.equal(env.NEWSLETTERS.values.size, 0);

  const kept = await worker.fetch(post({ from: " a@example.org ", text: " Hello " }, "write-1"), env);
  assert.equal(kept.status, 201);
  assert.equal((await worker.fetch(read("write-1"), env)).status, 401);   // the write token cannot read
  const [message, ...rest] = await inbox(env);
  assert.equal(rest.length, 0);
  assert.ok(message.thread && message.id);
  assert.deepEqual({ ...message, at: "", thread: "", id: "" }, {
    from: "a@example.org", address: "a@example.org", subject: "", at: "", text: "Hello", via: "form", thread: "", id: "",
    direction: "in", attachments: [],
  });
});

test("the contact routes refuse to work while any two of the read, write and scan tokens are the same", async () => {
  for (const same of [{ CONTACT_READ_TOKEN: "write-1" }, { CONTACT_SCAN_TOKEN: "read-1" }, { CONTACT_SCAN_TOKEN: "write-1" }]) {
    const env = environment(same);
    assert.equal((await worker.fetch(post({ from: "a@example.org", text: "Hello" }, "write-1"), env)).status, 503);
    assert.equal((await worker.fetch(read("read-1"), env)).status, 503);
    assert.equal((await worker.fetch(call("/contact/reply", { method: "POST", body: { thread: "t", text: "x" }, token: "read-1" }), env)).status, 503);
    assert.equal((await worker.fetch(call("/contact/attachments?scan=pending", { token: "scan-1" }), env)).status, 503);
    assert.equal(env.NEWSLETTERS.values.size, 0);
  }
});

const reply = (thread, text, token = "read-1") => call("/contact/reply", { method: "POST", body: { thread, text }, token });

test("a reply goes only to the thread's correspondent, threaded, and the answer to it joins the same thread", async () => {
  const env = environment();
  await worker.email(email("A Person <a@example.org>", "Data access", "Message-ID: <first@a.example>\r\n"), env);
  const [first] = await inbox(env);
  assert.equal(first.message_id, "<first@a.example>");

  assert.equal((await worker.fetch(reply(first.thread, "Thanks", "write-1"), env)).status, 401);
  assert.equal((await worker.fetch(reply("no-such-thread", "Thanks"), env)).status, 404);
  assert.equal((await worker.fetch(reply(first.thread, "   "), env)).status, 400);
  // a recipient in the body is ignored: the reply goes to the thread's correspondent only
  const sent = await worker.fetch(call("/contact/reply", {
    method: "POST", token: "read-1", body: { thread: first.thread, text: "Thanks, here it is.", to: "victim@example.net" },
  }), env);
  assert.equal(sent.status, 201);
  assert.deepEqual(env.EMAIL.sent, [{
    to: "a@example.org", from: { email: "contact@opengnss.org", name: "OpenGNSS" }, subject: "Re: Data access", text: "Thanks, here it is.",
    headers: { "In-Reply-To": "<first@a.example>", References: "<first@a.example>" },
  }]);

  // their answer names our reply in In-Reply-To
  await worker.email(email("a@example.org", "Re: Data access",
    "Message-ID: <second@a.example>\r\nIn-Reply-To: <sent-1@cf.example>\r\nReferences: <first@a.example> <sent-1@cf.example>\r\n"), env);
  // and an unrelated email starts a thread of its own
  await worker.email(email("b@example.org", "Other", "Message-ID: <other@b.example>\r\n"), env);
  const messages = await inbox(env);
  const thread = messages.filter((m) => m.thread === first.thread).map((m) => [m.direction, m.message_id]);
  assert.deepEqual(thread.sort(), [["in", "<first@a.example>"], ["in", "<second@a.example>"], ["out", "<sent-1@cf.example>"]]);
  assert.equal(messages.find((m) => m.address === "b@example.org").thread === first.thread, false);
  const out = messages.find((m) => m.direction === "out");
  assert.equal(out.to, "a@example.org");
  assert.equal(out.text, "Thanks, here it is.");
});

test("a reply says plainly why it was not sent: no EMAIL binding, or Email Service refusing", async () => {
  const env = environment({ EMAIL: undefined });
  await worker.fetch(post({ from: "a@example.org", text: "Hello" }, "write-1"), env);
  const [message] = await inbox(env);
  const unset = await worker.fetch(reply(message.thread, "Hi"), env);
  assert.equal(unset.status, 503);
  assert.match((await unset.json()).problem, /email sending is not set up/);

  env.EMAIL = { async send() { throw Object.assign(new Error("domain not onboarded"), { code: "E_SENDER_DOMAIN_NOT_AVAILABLE" }); } };
  const refused = await worker.fetch(reply(message.thread, "Hi"), env);
  assert.equal(refused.status, 502);
  assert.equal((await refused.json()).problem, "email not sent (E_SENDER_DOMAIN_NOT_AVAILABLE): domain not onboarded");
  assert.equal((await inbox(env)).length, 1);   // nothing kept that was not sent
});

const attachment = (id, token, suffix = "") => call(`/contact/attachments/${id}${suffix}`, { token });
const verdict = (id, body, token = "scan-1") => call(`/contact/attachments/${id}/scan`, { method: "POST", body, token });

test("an attachment waits for its scan: the console cannot download it until it is clean", async () => {
  const env = environment();
  const files = [{ name: "plan.pdf", content: btoa("%PDF-1.4 plan") }, { name: "data.csv", content: btoa("a,b\n1,2\n") }];
  assert.equal((await worker.fetch(post({ from: "a@example.org", text: "See attached", attachments: files }, "write-1"), env)).status, 201);
  const [message] = await inbox(env);
  assert.deepEqual(message.attachments.map((a) => [a.name, a.type, a.size, a.scan]), [
    ["plan.pdf", "application/pdf", 13, "pending"], ["data.csv", "text/csv", 8, "pending"]]);
  const [pdf, csv] = message.attachments;

  assert.equal((await worker.fetch(call("/contact/attachments?scan=pending", { token: "read-1" }), env)).status, 401);
  const pending = await (await worker.fetch(call("/contact/attachments?scan=pending", { token: "scan-1" }), env)).json();
  assert.deepEqual(pending.map((f) => f.id).sort(), [pdf.id, csv.id].sort());

  const early = await worker.fetch(attachment(pdf.id, "read-1"), env);
  assert.equal(early.status, 409);
  assert.deepEqual(await early.json(), { ok: false, scan: "pending" });
  assert.equal((await worker.fetch(attachment(pdf.id, "write-1"), env)).status, 401);
  assert.equal(await (await worker.fetch(attachment(pdf.id, "scan-1"), env)).text(), "%PDF-1.4 plan");   // the scanner can fetch it

  assert.equal((await worker.fetch(verdict(pdf.id, { result: "clean" }, "read-1"), env)).status, 401);
  assert.equal((await worker.fetch(verdict(pdf.id, { result: "perhaps" }), env)).status, 400);
  assert.equal((await worker.fetch(verdict(pdf.id, { result: "clean" }), env)).status, 200);
  const clean = await worker.fetch(attachment(pdf.id, "read-1"), env);
  assert.equal(clean.status, 200);
  assert.equal(await clean.text(), "%PDF-1.4 plan");
  assert.equal(clean.headers.get("content-type"), "application/pdf");
  assert.equal(clean.headers.get("content-disposition"), "attachment; filename*=UTF-8''plan.pdf");
  // a leaked scan token can neither fetch a clean file nor remove it
  assert.equal((await worker.fetch(attachment(pdf.id, "scan-1"), env)).status, 409);
  assert.equal((await worker.fetch(verdict(pdf.id, { result: "infected", signature: "x" }), env)).status, 409);
  assert.equal(await (await worker.fetch(attachment(pdf.id, "read-1"), env)).text(), "%PDF-1.4 plan");

  assert.equal((await worker.fetch(verdict(csv.id, { result: "infected", signature: "Eicar-Test-Signature" }), env)).status, 200);
  assert.equal(env.NEWSLETTERS.values.get(`contact-file:${csv.id}`), "");   // the bytes are gone
  for (const token of ["read-1", "scan-1"]) {
    const removed = await worker.fetch(attachment(csv.id, token), env);
    assert.equal(removed.status, 409);
    assert.deepEqual(await removed.json(), { ok: false, scan: "infected" });
  }
  assert.equal((await worker.fetch(verdict(csv.id, { result: "clean" }), env)).status, 409);   // not brought back
  const [after] = await inbox(env);
  assert.deepEqual(after.attachments.map((a) => [a.scan, a.signature]), [["clean", ""], ["infected", "Eicar-Test-Signature"]]);
  assert.deepEqual(await (await worker.fetch(call("/contact/attachments?scan=pending", { token: "scan-1" }), env)).json(), []);
});

test("the form's attachments are refused past the limits, and nothing is kept", async () => {
  const env = environment();
  const tooMany = Array(4).fill({ name: "a.txt", content: btoa("x") });
  const answer = await worker.fetch(post({ from: "a@example.org", text: "Hi", attachments: tooMany }, "write-1"), env);
  assert.equal(answer.status, 400);
  assert.match((await answer.json()).problem, /more than 3/);
  assert.equal((await worker.fetch(post({ from: "a@example.org", text: "Hi", attachments: [{ name: "x.exe", content: "" }] }, "write-1"), env)).status, 400);
  assert.equal(env.NEWSLETTERS.values.size, 0);
});

test("an email's attachment is kept for scanning; one of a type not accepted is only noted", async () => {
  const env = environment();
  await worker.email(email("a@example.org", "Report", "", "report.pdf"), env);
  await worker.email(email("b@example.org", "Program", "", "setup.exe"), env);
  const messages = await inbox(env);
  const kept = messages.find((m) => m.address === "a@example.org").attachments;
  assert.deepEqual(kept.map((a) => [a.name, a.type, a.scan]), [["report.pdf", "application/pdf", "pending"]]);
  assert.equal(await (await worker.fetch(attachment(kept[0].id, "scan-1"), env)).text(), "%PDF-1.4 test");
  assert.deepEqual(messages.find((m) => m.address === "b@example.org").attachments, [{ name: "setup.exe", size: 13, note: "not kept: type not accepted" }]);
});

test("a subject with line breaks is kept on one line, so a reply can never carry an extra header", async () => {
  const env = environment();
  await worker.fetch(post({ from: "a@example.org", subject: "Hello\r\nBcc: someone@example.net", text: "Hi" }, "write-1"), env);
  const [message] = await inbox(env);
  assert.equal(message.subject, "Hello Bcc: someone@example.net");
  assert.equal((await worker.fetch(call("/contact/reply", { method: "POST", body: { thread: message.thread, text: "Thanks" }, token: "read-1" }), env)).status, 201);
  assert.equal(env.EMAIL.sent[0].subject, "Re: Hello Bcc: someone@example.net");
  assert.equal(env.EMAIL.sent[0].to, "a@example.org");
});

test("the inbox takes at most its daily number of messages, form and mail together", async () => {
  const { CONTACT_DAILY_MESSAGES } = await import("./lib.js");
  const env = environment();
  for (let i = 0; i < CONTACT_DAILY_MESSAGES; i++) {
    assert.equal((await worker.fetch(post({ from: "a@example.org", text: `n${i}` }, "write-1"), env)).status, 201);
  }
  const full = await worker.fetch(post({ from: "a@example.org", text: "one more" }, "write-1"), env);
  assert.equal(full.status, 429);
  let rejected = "";
  await worker.email({ ...email("b@example.org", "Hi"), setReject: (why) => { rejected = why; } }, env);
  assert.match(rejected, /full for today/);
  assert.equal((await inbox(env)).length, CONTACT_DAILY_MESSAGES);
});

// The Worker's contact routes end to end, with an in-memory stand-in for its KV store. Run: node --test cloudflare/newsletters/
import assert from "node:assert/strict";
import { test } from "node:test";
import worker from "./worker.js";

function store() {
  const values = new Map();
  return {
    values,
    async put(key, value) { values.set(key, value); },
    async get(key, type) { const value = values.get(key); return value && type === "json" ? JSON.parse(value) : value ?? null; },
    async list({ prefix }) { return { keys: [...values.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })), list_complete: true }; },
  };
}

const post = (body, token) => new Request("https://feeds.opengnss.org/contact", {
  method: "POST", body: typeof body === "string" ? body : JSON.stringify(body),
  headers: token ? { authorization: `Bearer ${token}` } : {},
});
const read = (token) => new Request("https://feeds.opengnss.org/contact", { headers: { authorization: `Bearer ${token}` } });

test("a form message with the write token is kept in the inbox, marked as from the form, and read back with the read token", async () => {
  const env = { NEWSLETTERS: store(), CONTACT_WRITE_TOKEN: "write-1", CONTACT_READ_TOKEN: "read-1" };
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
  const inbox = await (await worker.fetch(read("read-1"), env)).json();
  assert.equal(inbox.length, 1);
  assert.deepEqual({ ...inbox[0], at: "" }, { from: "a@example.org", subject: "", at: "", text: "Hello", via: "form" });
});

test("the contact routes refuse to work while the read and write tokens are the same", async () => {
  const env = { NEWSLETTERS: store(), CONTACT_WRITE_TOKEN: "same", CONTACT_READ_TOKEN: "same" };
  assert.equal((await worker.fetch(post({ from: "a@example.org", text: "Hello" }, "same"), env)).status, 503);
  assert.equal((await worker.fetch(read("same"), env)).status, 503);
  assert.equal(env.NEWSLETTERS.values.size, 0);
});

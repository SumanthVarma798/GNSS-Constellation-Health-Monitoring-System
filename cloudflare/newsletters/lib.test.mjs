// Run: node --test cloudflare/newsletters/
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  CONTACT_TEXT_CHARACTERS, authorized, contactRecord, excerpt, formMessage, fromSubstack, isContact, newestFirst, plainText, postLink, publicationOf,
  receiverResults, rss,
} from "./lib.js";

test("only mail to the contact address goes to the contact inbox", () => {
  assert.equal(isContact("Contact@OpenGNSS.org", undefined), true);
  assert.equal(isContact("newsletters@feeds.opengnss.org", undefined), false);
  assert.equal(isContact("hello@opengnss.org", "hello@opengnss.org"), true);
  assert.equal(isContact("contact@opengnss.org", "hello@opengnss.org"), false);
  assert.equal(isContact(undefined, undefined), false);
});

test("a contact message keeps who wrote, the subject, when, and its plain text trimmed", () => {
  const at = "2026-11-16T10:00:00.000Z";
  const kept = contactRecord({ from: { name: "A Person", address: "a@example.org" }, subject: "Working together", text: "  Hello  " }, "bounce@x", at);
  assert.deepEqual(kept, { from: "A Person <a@example.org>", subject: "Working together", at, text: "Hello" });
  assert.equal(contactRecord({ text: "x".repeat(9000) }, "env@example.org", at).text.length, CONTACT_TEXT_CHARACTERS);
  const htmlOnly = contactRecord({ html: "<p>Hi <b>there</b></p>" }, "env@example.org", at);
  assert.equal(htmlOnly.from, "env@example.org");
  assert.equal(htmlOnly.subject, "");
  assert.equal(htmlOnly.text, "Hi there");
});

test("a contact-form message is kept trimmed, or refused with a short reason", () => {
  assert.deepEqual(formMessage({ from: " a@example.org ", text: "  Hello  " }), { from: "a@example.org", subject: "", text: "Hello" });
  assert.deepEqual(formMessage({ from: "a@example.org", subject: "Hi", text: "x" }), { from: "a@example.org", subject: "Hi", text: "x" });
  for (const body of [null, "text", 42]) assert.ok(formMessage(body).problem);
  assert.match(formMessage({ text: "x" }).problem, /from/);
  assert.match(formMessage({ from: "not an address", text: "x" }).problem, /from/);
  assert.match(formMessage({ from: "A <a@example.org>", text: "x" }).problem, /from/);
  assert.match(formMessage({ from: `${"a".repeat(250)}@example.org`, text: "x" }).problem, /from/);
  assert.match(formMessage({ from: "a@example.org", subject: "s".repeat(201), text: "x" }).problem, /subject/);
  assert.match(formMessage({ from: "a@example.org", text: "   " }).problem, /empty/);
  assert.match(formMessage({ from: "a@example.org", text: 7 }).problem, /empty/);
  assert.equal(formMessage({ from: "a@example.org", text: "x".repeat(CONTACT_TEXT_CHARACTERS) }).text.length, CONTACT_TEXT_CHARACTERS);
  assert.match(formMessage({ from: "a@example.org", text: "x".repeat(CONTACT_TEXT_CHARACTERS + 1) }).problem, /longer/);
});

test("the contact inbox opens only for the right bearer token", () => {
  assert.equal(authorized("Bearer s3cret", "s3cret"), true);
  assert.equal(authorized("Bearer s3cres", "s3cret"), false);
  assert.equal(authorized("Bearer s3cret-and-more", "s3cret"), false);
  assert.equal(authorized("s3cret", "s3cret"), false);
  assert.equal(authorized(null, "s3cret"), false);
  assert.equal(authorized("Bearer ", ""), false);          // no token set: no one is let in
  assert.equal(authorized("Bearer undefined", undefined), false);
});

test("the newest contact messages come first, at most the limit", () => {
  const names = ["contact:2026-11-01T00:00:00.000Z:a", "contact:2026-11-03T00:00:00.000Z:c", "contact:2026-11-02T00:00:00.000Z:b"];
  assert.deepEqual(newestFirst(names, 2), [names[1], names[2]]);
});

const SIGNED = "mx.cloudflare.net; dkim=pass header.d=substack.com header.s=s1; spf=pass";

test("only mail Substack signed is accepted", () => {
  assert.equal(fromSubstack("China Space Monitor <chinaspacemonitor@substack.com>", SIGNED), true);
  assert.equal(fromSubstack("someone@gmail.com", SIGNED), false);
  assert.equal(fromSubstack("chinaspacemonitor@substack.com", "dkim=fail header.d=substack.com"), false);
  assert.equal(fromSubstack("chinaspacemonitor@substack.com", ""), false);
});

test("only the results our own server added are trusted, not a header the sender wrote", () => {
  const forged = { key: "Authentication-Results", value: "evil.example; dkim=pass header.d=substack.com" };
  const ours = { key: "ARC-Authentication-Results", value: "i=1; mx.cloudflare.net; dkim=pass header.d=substack.com" };
  assert.equal(receiverResults([ours, forged]), ours.value);
  assert.equal(receiverResults([forged]), "");
  assert.equal(fromSubstack("x@substack.com", receiverResults([forged])), false);
});

test("a welcome email listing several posts is not taken for a post", () => {
  const a = "https://pub.substack.com/p/first ", b = "https://pub.substack.com/p/second ";
  assert.equal(postLink("pub", a + b + a + b), "");
  assert.equal(postLink("pub", a + a + a + b), "https://pub.substack.com/p/first");
  assert.equal(postLink("pub", a + a), "");
});

test("the publication and the post's clean link are found; tracking is dropped", () => {
  const post = "https://chinaspacemonitor.substack.com/p/beidou-update?utm_source=x ";
  const text = "Read it https://substack.com/redirect/abc?token=secret and " + post.repeat(3);
  const publication = publicationOf({ "list-url": "<https://chinaspacemonitor.substack.com/>" }, text);
  assert.equal(publication, "chinaspacemonitor");
  assert.equal(postLink(publication, text), "https://chinaspacemonitor.substack.com/p/beidou-update");
  assert.equal(postLink("other", text), "");
  assert.equal(publicationOf({}, "no links here"), "");
});

test("the excerpt is short, has no links, and the feed escapes everything", () => {
  assert.ok(excerpt("word ".repeat(200)).length <= 301);
  assert.equal(excerpt("see https://x.example/a now"), "see now");
  const feed = rss("pub", [{ title: "A <b> & 'c'", link: "https://pub.substack.com/p/a", date: "2026-10-27T00:00:00Z", excerpt: "x" }]);
  assert.match(feed, /A &lt;b&gt; &amp; &apos;c&apos;/);
  assert.match(feed, /<pubDate>Tue, 27 Oct 2026 00:00:00 GMT<\/pubDate>/);
});

test("an HTML-only contact message keeps its words, not its style sheet, with entities read back", () => {
  assert.equal(plainText("<style>.x{display:none}</style><p>AT&amp;T &lt;3</p>").trim(), "AT&T <3");
  assert.equal(contactRecord({ html: "<script>x()</script><b>Hi</b>" }, "a@b", "t").text, "Hi");
});

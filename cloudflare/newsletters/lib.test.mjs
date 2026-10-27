// Run: node --test cloudflare/newsletters/
import assert from "node:assert/strict";
import { test } from "node:test";
import { excerpt, fromSubstack, postLink, publicationOf, receiverResults, rss } from "./lib.js";

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

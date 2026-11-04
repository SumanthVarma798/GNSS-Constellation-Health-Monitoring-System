// The newsletters Worker (issue 152). Receives mail sent to newsletters@feeds.opengnss.org and serves
// https://feeds.opengnss.org/substack/<publication>/feed, which the archive job reads like any other feed.
// Only mail that Substack signed (DKIM) is kept. The raw email stays private in KV; the feed carries only the title,
// the post's public link, the date and a short excerpt.
import PostalMime from "postal-mime";
import { FEED_ITEMS, excerpt, fromSubstack, postLink, publicationOf, receiverResults, rss } from "./lib.js";

export default {
  async email(message, env) {
    const raw = await new Response(message.raw).arrayBuffer();
    const mail = await PostalMime.parse(raw);
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
    const found = new URL(request.url).pathname.match(/^\/substack\/([a-z0-9-]+)\/feed\/?$/);
    if (!found) return new Response("OpenGNSS feeds. See https://github.com/SumanthVarma798/GNSS-Constellation-Health-Monitoring-System\n");
    const keys = [];
    let cursor;
    do {   // ponytail: lists every key of the publication each read; keep a per-publication index if that grows slow
      const page = await env.NEWSLETTERS.list({ prefix: `post:${found[1]}:`, cursor });
      keys.push(...page.keys.map((k) => k.name));
      cursor = page.list_complete ? undefined : page.cursor;
    } while (cursor);
    const newest = keys.sort().reverse().slice(0, FEED_ITEMS);
    const posts = (await Promise.all(newest.map((name) => env.NEWSLETTERS.get(name, "json")))).filter(Boolean);
    return new Response(rss(found[1], posts), { headers: { "content-type": "application/rss+xml; charset=utf-8" } });
  },
};

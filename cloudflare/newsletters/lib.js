// Pure helpers for the newsletters Worker: who sent a newsletter, which post it is, and the RSS the archive reads.
// Substack refuses GitHub's servers, so its posts reach the archive by email instead (issue 152).

export const EXCERPT_CHARACTERS = 300;   // like the dashboard's summary: a pointer to the post, never the whole text
export const FEED_ITEMS = 50;            // newest posts kept in each publication's feed

const POST_LINK = /https:\/\/([a-z0-9-]+)\.substack\.com\/p\/([a-z0-9-]+)/i;

// The publication a Substack newsletter belongs to ("chinaspacemonitor"), or "" when it is not a Substack post.
export function publicationOf(headers, text) {
  const listUrl = headers["list-url"] || headers["list-post"] || "";
  const fromList = listUrl.match(/https?:\/\/([a-z0-9-]+)\.substack\.com/i);
  if (fromList) return fromList[1].toLowerCase();
  const fromLink = (text || "").match(POST_LINK);
  return fromLink ? fromLink[1].toLowerCase() : "";
}

export const POST_LINK_REPEATS = 3;   // a post's email links its own page several times (title, read in app, comments)

// The post's own public address, with no tracking or subscriber token, or "" when the email is not one post.
// A welcome email lists several posts once or twice each, so one slug must clearly lead.
// ponytail: a heuristic from how Substack lays out its emails; a dedicated header would be firmer if one is found.
export function postLink(publication, text) {
  const counts = new Map();
  for (const match of (text || "").matchAll(new RegExp(POST_LINK, "gi"))) {
    if (match[1].toLowerCase() === publication) counts.set(match[2], (counts.get(match[2]) || 0) + 1);
  }
  const [first, second] = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  if (!first || first[1] < POST_LINK_REPEATS || (second && second[1] >= first[1])) return "";
  return `https://${publication}.substack.com/p/${first[0]}`;
}

// The results Cloudflare's own mail server added: the topmost ARC or Authentication-Results header naming
// mx.cloudflare.net. A sender can add headers of the same name, but only below the ones our server prepends.
export function receiverResults(headers) {
  for (const name of ["arc-authentication-results", "authentication-results"]) {
    const top = headers.find((h) => h.key.toLowerCase() === name);
    if (top && /^\s*(i=\d+\s*;\s*)?mx\.cloudflare\.net\b/i.test(top.value)) return top.value;
  }
  return "";
}

// True only when our receiving server saw a passing DKIM signature from substack.com.
export function fromSubstack(from, results) {
  const sender = (from || "").toLowerCase();
  const signed = /dkim=pass[^;]*header\.(d|i)=@?(?:[a-z0-9-]+\.)*substack\.com/i.test(results || "");
  return /@([a-z0-9-]+\.)*substack\.com>?$/.test(sender) && signed;
}

export function excerpt(text) {
  const words = (text || "").replace(/https?:\/\/\S+/g, "").replace(/\s+/g, " ").trim();
  if (words.length <= EXCERPT_CHARACTERS) return words;
  return words.slice(0, EXCERPT_CHARACTERS).replace(/\s+\S*$/, "") + "…";
}

const escapeXml = (value) => String(value).replace(/[<>&'"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;" })[c]);

// RSS 2.0 for one publication's posts, newest first.
export function rss(publication, posts) {
  const items = posts.map((post) => `<item><title>${escapeXml(post.title)}</title><link>${escapeXml(post.link)}</link>`
    + `<guid isPermaLink="true">${escapeXml(post.link)}</guid><pubDate>${new Date(post.date).toUTCString()}</pubDate>`
    + `<description>${escapeXml(post.excerpt)}</description></item>`).join("");
  return `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>${escapeXml(publication)} (by email)</title>`
    + `<link>https://${escapeXml(publication)}.substack.com/</link><description>Posts received by email; each links to the original.</description>`
    + `${items}</channel></rss>`;
}

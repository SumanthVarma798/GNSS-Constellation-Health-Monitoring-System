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

// The contact inbox: mail to contact@opengnss.org is kept privately for the team to read in the console, never published.
export const CONTACT_TO = "contact@opengnss.org";   // the default; the Worker's CONTACT_TO var overrides it
export const CONTACT_TEXT_CHARACTERS = 4000;
export const CONTACT_READ_ITEMS = 200;             // the newest messages GET /contact returns

export const isContact = (to, contactTo) => (to || "").trim().toLowerCase() === (contactTo || CONTACT_TO).trim().toLowerCase();

// An HTML-only message as plain words: no style or script text, the common entities read back.
const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'", apos: "'", nbsp: " " };
export const plainText = (html) => html
  .replace(/<(style|script)\b[^>]*>[\s\S]*?<\/\1>/gi, " ")
  .replace(/<[^>]*>/g, " ")
  .replace(/&(amp|lt|gt|quot|#39|apos|nbsp);/g, (_, name) => ENTITIES[name])
  .replace(/[ \t]+/g, " ");

// What is kept of one message: who wrote (as shown, and the bare address a reply goes to), the subject, when it
// arrived, and its plain text, trimmed.
export function contactRecord(mail, envelopeFrom, at) {
  const address = (mail.from && mail.from.address) || envelopeFrom || "";
  const from = mail.from && mail.from.address && mail.from.name ? `${mail.from.name} <${address}>` : address;
  const text = mail.text || plainText(mail.html || "");
  return { from, address, subject: mail.subject || "", at, text: Array.from(text.trim()).slice(0, CONTACT_TEXT_CHARACTERS).join("") };
}

// ---- threads: every message carries `thread` (an id) and `direction` ("in" from a correspondent, "out" from us) ----

// The Message-IDs in a header value ("<a@x> <b@y>"), lowercased so they compare as mail clients compare them.
export const messageIds = (value) => (String(value || "").match(/<[^<>\s]+>/g) || []).map((id) => id.toLowerCase());

// An id as a Message-ID header carries it: in angle brackets.
export const asMessageId = (id) => (!id ? "" : String(id).startsWith("<") ? String(id) : `<${id}>`);

// The thread an inbound email joins: the one holding a message its In-Reply-To or References names, else "" (a new one).
// References matters as much as In-Reply-To: a reply to our reply still names the correspondent's first message there.
export function threadOf(mail, records) {
  const named = new Set(messageIds(`${mail.inReplyTo || ""} ${mail.references || ""}`));
  const found = named.size && records.find((r) => r.message_id && messageIds(r.message_id).some((id) => named.has(id)));
  return found ? found.thread : "";
}

export const REPLY_SUBJECT_DEFAULT = "your message to OpenGNSS";   // a form message has no subject
export const HEADER_VALUE_BYTES = 2048;                           // Email Service's limit on one header's value

// What a reply in `thread` needs: {to, subject, headers}, or {status, problem}. It goes only to the address that wrote to
// us first in the thread, never to one the caller names, so a leaked token cannot turn the Worker into a relay.
export function replyTo(records, thread, text) {
  const words = typeof text === "string" ? text.trim() : "";
  if (!words) return { status: 400, problem: "text is empty" };
  if (characters(words) > CONTACT_TEXT_CHARACTERS) return { status: 400, problem: `text is longer than ${CONTACT_TEXT_CHARACTERS} characters` };
  const oldestFirst = records.filter((r) => r.thread === thread).sort((a, b) => (a.at < b.at ? -1 : 1));
  if (!oldestFirst.length) return { status: 404, problem: "no such thread" };
  const first = oldestFirst.find((r) => r.direction === "in");
  if (!first || !PLAUSIBLE_ADDRESS.test(first.address || "")) return { status: 409, problem: "the thread has no address to reply to" };
  const subject = oldestFirst[0].subject || "";
  const headers = {};
  const last = [...oldestFirst].reverse().find((r) => r.direction === "in" && r.message_id);
  if (last) {
    const chain = [...messageIds(last.references), ...messageIds(last.message_id)];
    while (chain.length > 1 && new TextEncoder().encode(chain.join(" ")).length > HEADER_VALUE_BYTES) chain.splice(1, 1);   // keep the first and the newest
    headers["In-Reply-To"] = asMessageId(last.message_id);
    headers.References = chain.join(" ");
  }
  return { to: first.address, subject: /^re:/i.test(subject) ? subject : `Re: ${subject || REPLY_SUBJECT_DEFAULT}`, headers, text: words };
}

// ---- attachments: kept beside the message, each scanned for viruses before anyone can download it ----

export const ATTACHMENT_FILES = 3;
export const ATTACHMENT_BYTES = 5 * 1024 * 1024;   // a message's files together
export const ATTACHMENT_NAME_CHARACTERS = 100;
export const SIGNATURE_CHARACTERS = 200;
// By name, never by the type a sender claims; a download is served as this type.
export const ATTACHMENT_TYPES = {
  pdf: "application/pdf", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp",
  txt: "text/plain", csv: "text/csv", json: "application/json",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};
export const SCAN_STATES = ["pending", "clean", "infected"];

export const fileType = (name) => ATTACHMENT_TYPES[(String(name || "").match(/\.([a-z0-9]+)$/i) || [])[1]?.toLowerCase()] || "";

// A name safe to show and to download under: no folders, no control characters, not too long.
export const safeName = (name) =>
  Array.from(String(name || "").replace(/[\u0000-\u001f\u007f/\\]/g, "_").trim()).slice(0, ATTACHMENT_NAME_CHARACTERS).join("") || "attachment";

// An email's attachments ([{name, content}]) split into those kept and those only noted, under the form's limits.
export function sortAttachments(files) {
  const kept = [], noted = [];
  let bytes = 0;
  for (const file of files) {
    const size = file.content.byteLength ?? file.content.length, name = safeName(file.name), type = fileType(file.name);
    const note = !type ? "not kept: type not accepted"
      : kept.length >= ATTACHMENT_FILES ? `not kept: more than ${ATTACHMENT_FILES} files`
        : bytes + size > ATTACHMENT_BYTES ? "not kept: too large" : "";
    if (note) noted.push({ name, size, note });
    else { kept.push({ name, type, size, content: file.content }); bytes += size; }
  }
  return { kept, noted };
}

const BASE64 = /^[A-Za-z0-9+/]*={0,2}$/;

// The form's attachments ([{name, content (base64)}], at most 3, 5 MB in all), as [{name, type, size, content}], or
// {problem}. The dashboard checks the same first, so a refusal here means something else sent it.
export function formAttachments(list) {
  if (list === undefined) return { files: [] };
  if (!Array.isArray(list)) return { problem: "attachments must be a list" };
  if (list.length > ATTACHMENT_FILES) return { problem: `more than ${ATTACHMENT_FILES} attachments` };
  const files = [];
  let bytes = 0;
  for (const item of list) {
    const content = item && typeof item.content === "string" ? item.content : "";
    if (!item || typeof item.name !== "string" || !fileType(item.name)) return { problem: "an attachment's type is not accepted" };
    if (content.length % 4 || !BASE64.test(content)) return { problem: "an attachment is not base64" };
    bytes += content.length / 4 * 3 - (content.match(/=*$/)[0].length);
    if (bytes > ATTACHMENT_BYTES) return { problem: "the attachments are larger than 5 MB in all" };
    files.push({ name: safeName(item.name), type: fileType(item.name), content });
  }
  return {
    files: files.map((f) => {
      const content = Uint8Array.from(atob(f.content), (c) => c.charCodeAt(0));
      return { ...f, size: content.byteLength, content };
    }),
  };
}

// A scanner's verdict (POST /contact/attachments/<id>/scan): {result, signature} or {problem}.
export function scanResult(body) {
  const result = body && body.result;
  if (result !== "clean" && result !== "infected") return { problem: 'result must be "clean" or "infected"' };
  const signature = typeof body.signature === "string" ? Array.from(body.signature.trim()).slice(0, SIGNATURE_CHARACTERS).join("") : "";
  return { result, signature: result === "infected" ? signature || "unnamed" : "" };
}

// Characters as the dashboard counts them (Python's len): an emoji is one, not the two UTF-16 units .length counts.
const characters = (value) => Array.from(value).length;

// A message from the dashboard's contact form (POST /contact): {from, subject?, text}.
// Returns {from, subject, text} trimmed, or {problem} saying in a few words why it is refused.
export const CONTACT_ADDRESS_CHARACTERS = 254;
export const CONTACT_SUBJECT_CHARACTERS = 200;
const PLAUSIBLE_ADDRESS = /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/;

export function formMessage(body) {
  const field = (name) => (body && typeof body[name] === "string" ? body[name].trim() : "");
  const from = field("from"), subject = field("subject"), text = field("text");
  if (!body || typeof body !== "object") return { problem: "the message must be JSON" };
  if (characters(from) > CONTACT_ADDRESS_CHARACTERS || !PLAUSIBLE_ADDRESS.test(from)) return { problem: "from is not an email address" };
  if (characters(subject) > CONTACT_SUBJECT_CHARACTERS) return { problem: `subject is longer than ${CONTACT_SUBJECT_CHARACTERS} characters` };
  if (!text) return { problem: "text is empty" };
  if (characters(text) > CONTACT_TEXT_CHARACTERS) return { problem: `text is longer than ${CONTACT_TEXT_CHARACTERS} characters` };
  return { from, subject, text };
}

// The public dashboard holds the write token and a GitHub job the scan token; were either the read token too, one leak
// would open the whole inbox. So the contact routes refuse to work at all while any two of the three that are set match.
export function sameTokens(env) {
  const set = [env.CONTACT_READ_TOKEN, env.CONTACT_WRITE_TOKEN, env.CONTACT_SCAN_TOKEN].filter(Boolean);
  return new Set(set).size < set.length;
}

// True only for "Bearer <token>" with the configured token. Every byte is compared whatever the input, so the time taken
// does not tell how much of a guess was right. No token configured means no one is let in.
export function authorized(header, token) {
  if (!token) return false;
  const encoder = new TextEncoder();
  const given = encoder.encode(header || ""), wanted = encoder.encode(`Bearer ${token}`);
  let difference = given.length ^ wanted.length;
  for (let i = 0; i < wanted.length; i++) difference |= (given[i] ?? 0) ^ wanted[i];
  return difference === 0;
}

// The newest keys first: an ISO time sorts as text.
export const newestFirst = (names, limit) => [...names].sort().reverse().slice(0, limit);

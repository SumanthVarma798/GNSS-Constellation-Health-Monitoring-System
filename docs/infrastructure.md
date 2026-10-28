# Infrastructure

What the project runs outside this repository, who holds it, and how to get it back. No secrets live here: only where
they are kept. Keep this page current whenever any of it changes.

## Domain: opengnss.org

| What | Value |
|---|---|
| Registrar | Cloudflare Registrar, in the Cloudflare account **OpenGNSS** (`16a8736db713b936302230f75fad84b2`) |
| Registered | 27 Oct 2026, for 1 year: **expires 27 Oct 2027** |
| Auto-renew | **Off**: someone must renew it by hand before it expires (it renews at about $11.20 a year) |
| Name servers | `grace.ns.cloudflare.com`, `vin.ns.cloudflare.com` |
| Public owner details | Redacted by Cloudflare; the registrant organisation is the OpenGNSS project |

The OpenGNSS account is the project's own, kept apart from anyone's personal Cloudflare account. Its admins:

- Sumanth Varma (Super Administrator)
- *A second Super Administrator is still to be invited, so the project never depends on one person.*

Every admin uses two-factor sign-in and keeps their recovery codes. To recover access, a remaining Super
Administrator re-invites the person; if none is left, Cloudflare support recovers the account from the billing owner.

## Names in use

| Name | What it is |
|---|---|
| `feeds.opengnss.org` (web) | The newsletters Worker: `https://feeds.opengnss.org/substack/<publication>/feed` |
| `feeds.opengnss.org` (mail) | Cloudflare Email Routing. Only `newsletters@feeds.opengnss.org` is accepted; all other addresses bounce |
| `dashboard.opengnss.org` | The dashboard (`dashboard.py`) on Render: a DNS-only CNAME to `opengnss-dashboard.onrender.com` |
| `console.opengnss.org` | The administration console (`admin.py`) on Render: a DNS-only CNAME to `opengnss-console.onrender.com` |
| `opengnss.org` | Unused for now; kept free for the project's site and the team's own mail |

## The dashboard and the console on Render

Streamlit Community Cloud cannot use our own domain, so both apps run on Render's free plan from
[render.yaml](../render.yaml): `opengnss-dashboard` and `opengnss-console`. Each redeploys on every commit to `main`,
except commits that only touch files it never reads (the dashboard skips docs, tests, the console and the Worker;
the console, whose assistant reads the docs and the code, skips only tests and the Worker). Each sleeps after 15
minutes with no visitors and takes about a minute to wake, so open them a minute before a demo. Free workspaces get
750 instance hours a month; sleeping services use none, so two mostly idle services fit.

The console's settings are a secret file in Render (**opengnss-console → Environment → Secret Files**, named
`secrets.toml`, laid out as `.streamlit/secrets.example.toml`); the start command copies it to where Streamlit reads
it. Its `[auth] redirect_uri` is `https://console.opengnss.org/oauth2callback`, and the Google OAuth client lists that
address as an authorised redirect URI.

To recreate them: in Render, **New → Blueprint**, pick this repository, apply, then add the console's secret file.
Each CNAME must stay DNS-only (grey cloud) so Render can issue its certificate.

## The newsletters Worker

Substack refuses GitHub's servers (403), so Substack posts reach the archive by email (issue 152):

1. A person subscribes `newsletters@feeds.opengnss.org` to each publication on Substack's own site.
2. Email Routing hands each message to the Worker `opengnss-newsletters` (`cloudflare/newsletters/`).
3. The Worker keeps only mail that Substack signed (DKIM), stores the raw message privately in the KV namespace
   `opengnss-newsletters`, and lists the post (title, public link, date, a 300-character excerpt) in that
   publication's feed. Sign-in and welcome mail is never published.
4. The archive job reads those feeds like any other (they are the Substack rows of `evidence/source_candidates.csv`).

Deploy a change from `cloudflare/newsletters/`: `npm ci`, `npm test`, then `npx wrangler deploy`. This needs a
Cloudflare sign-in (`npx wrangler login`) with access to the OpenGNSS account. Settings live in its `wrangler.toml`.

## Other accounts the project uses

| Service | Where | Secret kept in |
|---|---|---|
| GitHub (private mirror) | `SumanthVarma798/GNSS-Constellation-Health-Monitoring-System` and its `-archive` | repository secrets |
| twitterapi.io (X posts) | key named `TWITTERAPI_IO_KEY` | repository secret, given only to the archive job's `x` and `all` runs |
| Healthchecks.io | ping key `HEALTHCHECKS_PING_KEY` | repository secret |
| Render | the dashboard, service `opengnss-dashboard` | none needed yet |
| Render | the console, service `opengnss-console` | its secret file `secrets.toml` (sign-in, GitHub token, Space-Track, Healthchecks.io); see `.streamlit/secrets.example.toml` |

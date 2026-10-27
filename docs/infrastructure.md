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
| `dashboard.opengnss.org` | The dashboard (`dashboard.py`) on Render: a DNS-only CNAME to its `onrender.com` address |
| `opengnss.org` | Unused for now; kept free for the project's site and the team's own mail |

## The dashboard on Render

Streamlit Community Cloud cannot use our own domain, so the dashboard runs on Render's free plan from
[render.yaml](../render.yaml). It redeploys on every commit to `main`, except commits that only touch docs, tests,
the console or the Worker. It sleeps after 15 minutes with no visitors and takes about a minute to wake, so open it
a minute before a demo. Free workspaces get 750 instance hours a month, which covers one service running all month.

To recreate it: in Render, **New → Blueprint**, pick this repository, apply. The CNAME must stay DNS-only (grey
cloud) so Render can issue its certificate.

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
| Streamlit Community Cloud | the admin console | the app's own secrets |

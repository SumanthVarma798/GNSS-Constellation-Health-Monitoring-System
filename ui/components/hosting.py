"""How the project is hosted, for the administration console: names, providers and deploy paths in one picture.

The page is ui/components/hosting.html (plain JavaScript, no network); the words are here. They follow
docs/infrastructure.md and render.yaml as of Oct 2026. Text reaches the page as JSON escaped by embed() and is put in
with textContent, so it is never read as markup.
"""
from pathlib import Path

from ui.components.master_map import embed

PAGE_FILE = Path(__file__).with_name("hosting.html")

# Each part: (name, built | planned | key, in simple terms, key technical details, limits and risks, where it lives).
PARTS = {
    "brw": ("A visitor's browser", "built",
            "Someone opens dashboard.opengnss.org or console.opengnss.org in a normal web browser.",
            ["HTTPS to the hostname; DNS resolves through the project's Cloudflare account",
             "The browser talks only to Render for the app; it never sees GitHub or the archive"],
            ["The first request after idle waits about a minute while Render wakes the service"],
            "any web browser"),
    "dns": ("Cloudflare DNS: opengnss.org", "built",
            "The project's own Cloudflare account answers for every name under opengnss.org. DNS only (grey cloud), not proxied, for the two Streamlit apps.",
            ["Registered 27 Oct 2026; renew by hand before 27 Oct 2027",
             "dashboard.opengnss.org and console.opengnss.org are CNAMEs to Render",
             "feeds.opengnss.org points at the newsletters Worker"],
            ["One Cloudflare Super Administrator so far; a second is still to be invited",
             "Auto-renew is off for the domain"],
            "Cloudflare OpenGNSS account · docs/infrastructure.md"),
    "dhost": ("dashboard.opengnss.org", "built",
              "The public name for the team's satellite dashboard.",
              ["DNS-only CNAME to opengnss-dashboard.onrender.com",
               "TLS certificate issued by Render once DNS is correct"],
              ["If the CNAME is accidentally proxied (orange cloud), Render cannot renew its certificate"],
              "Cloudflare DNS record"),
    "rdash": ("Render: opengnss-dashboard", "built",
              "The dashboard app on Render's free plan: Streamlit running dashboard.py, rebuilt from main through render.yaml on each relevant push.",
              ["Start command runs streamlit on dashboard.py",
               "Sleeps after 15 minutes with no visitors; waking takes about a minute",
               "Orbits come bundled with the code; the News page fetches latest_news.json from the news-data branch over HTTPS when it opens",
               "CelesTrak refuses this server, so its newest orbits come from latest_gnss.json on the orbit-data branch"],
              ["750 instance hours per month shared across the workspace; two mostly idle services usually fit",
               "A cold start before a demo needs a minute's notice"],
              "render.yaml · dashboard.py"),
    "chost": ("console.opengnss.org", "built",
              "The public name for this administration console.",
              ["DNS-only CNAME to opengnss-console.onrender.com"],
              ["Same grey-cloud rule as the dashboard"],
              "Cloudflare DNS record"),
    "rcon": ("Render: opengnss-console", "key",
             "This console on Render's free plan: Streamlit running admin.py, Google sign-in with an allow-list, settings in a Render secret file never stored in the repository.",
             ["Start command runs streamlit on admin.py",
              "secrets.toml is a Render Secret File copied into place at start (see .streamlit/secrets.example.toml)",
              "Reads GitHub with its token: pull requests, issues, workflow runs, archive run logs",
              "Redeploys from main through render.yaml on every commit except test-only and Worker-only ones"],
             ["Same free-plan sleep and 750 shared instance hours as the dashboard",
              "The on-page assistant needs Ollama locally, so it is off on the shared copy"],
             "render.yaml · admin.py · console/"),
    "sub": ("A Substack newsletter email", "built",
            "Substack sends each post as email because its site refuses GitHub's servers (403).",
            ["A person subscribed newsletters@feeds.opengnss.org on Substack's site",
             "Only post mail is wanted; welcome and sign-in mail is discarded later"],
            ["If the subscription lapses, that publication stops arriving"],
            "Substack · issue 152"),
    "mail": ("Cloudflare Email Routing: newsletters@feeds.opengnss.org", "built",
             "Accepts only that one address on feeds.opengnss.org and forwards valid mail to the Worker.",
             ["All other addresses on the domain bounce",
              "Configured in the OpenGNSS Cloudflare account"],
             ["Misconfigured routing would drop newsletters silently until someone notices"],
             "Cloudflare Email Routing · docs/infrastructure.md"),
    "wrk": ("Cloudflare Worker: opengnss-newsletters", "built",
            "Receives routed mail, keeps only what Substack signed (DKIM), stores the raw message privately in KV, and publishes a public feed per publication.",
            ["Deploy from cloudflare/newsletters/ with wrangler",
             "Sign-in and welcome mail never published"],
            ["KV growth is unbounded until a retention policy is added",
             "Worker code changes need a Cloudflare login with access to OpenGNSS"],
            "cloudflare/newsletters/ · wrangler.toml"),
    "feed": ("feeds.opengnss.org/substack/<publication>/feed", "built",
             "Public Atom feeds the archive job reads like any other news source (Substack rows in source_candidates.csv).",
             ["One feed URL per Substack publication",
              "Lists title, link, date and a short excerpt"],
             ["If the Worker is down, Substack sources fail until it returns"],
             "cloudflare/newsletters/ · evidence/source_candidates.csv"),
    "repo": ("GitHub: this repository (main)", "built",
             "The private mirror where code, registry tables, workflows and decisions live.",
             ["Each push to main redeploys both Render services via render.yaml",
              "The dashboard skips commits that only touch docs, tests, Markdown, admin.py, the console or the Worker; the console skips only test-only and Worker-only commits"],
             ["GitHub outage blocks deploys and what the console reads live"],
             "GitHub · main branch"),
    "jobs": ("GitHub Actions: scheduled jobs", "built",
             "Timed workflows: archive (documents, catalogues, orbits, news, social, X), registry update, source record, orbit refresh and news-data jobs.",
             ["Archive runs on six schedules; registry rebuilds weekly",
              "The archive job also reads feeds.opengnss.org for Substack",
              "Writes to the -archive repository, the news-data branch (latest_news.json) and the orbit-data branch (latest_gnss.json)"],
             ["Scheduled runs can start late or be skipped on GitHub's side"],
             ".github/workflows/ · evidence/archive.py"),
    "arc": ("GitHub: the -archive repository", "built",
            "Private memory of every fetched copy and run logs the console can show.",
            ["Separate repository from main",
             "Archive workflow commits new copies and run summaries"],
            ["Grows without bound; object storage is parked until size matters"],
            "the …-archive repository · evidence/archive.py"),
    "news": ("the news-data branch: latest_news.json", "built",
             "Branch holding the latest bundled news snapshot the dashboard reads.",
             ["Updated by the news-data job on a schedule",
              "Not merged to main; the dashboard fetches latest_news.json from it over HTTPS"],
             ["If the job fails, the dashboard keeps the last snapshot it loaded"],
             "news-data branch · evidence/news.py"),
}


def payload():
    return {"parts": {key: {"name": p[0], "kind": p[1], "simple": p[2], "tech": p[3], "limits": p[4], "where": p[5]}
                      for key, p in PARTS.items()}}


def hosting_html(tokens_css, font):
    page = PAGE_FILE.read_text(encoding="utf-8").replace("__TOKENS__", tokens_css).replace("__FONT__", font)
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(payload())};", 1)

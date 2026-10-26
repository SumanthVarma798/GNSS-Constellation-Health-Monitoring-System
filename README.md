# Latest news for the dashboard

This branch holds one file, latest_news.json, written by the news run of .github/workflows/archive.yml
(job publish-news) every 3 hours, and committed only when it changed. The dashboard reads it from here,
so it needs no access to the private archive and main gets no commits from it. Never merge this branch.

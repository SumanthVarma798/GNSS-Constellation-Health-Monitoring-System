# OpenGNSS: GNSS Constellation Health Monitoring System

OpenGNSS watches the health of six navigation satellite systems: NavIC, QZSS, BeiDou, GPS, GLONASS
and Galileo: 148 satellites on 12 Nov 2026. It judges each satellite against its own slot or orbital
plane from public orbit records. It checks those records against the satellites' own broadcast orbits
in the IGS navigation files, and gathers news about each system. The results are shown on a public
dashboard.

| What | Address |
|---|---|
| Dashboard (`dashboard.py`) | <https://dashboard.opengnss.org> |
| Administration console (`admin.py`), for the team | <https://console.opengnss.org> |
| The team's earlier app (`app.py`) | <https://gnss-health-monitor.streamlit.app/> |
| What is planned, built and assumed | [docs/system-design.md](docs/system-design.md) |

Both sites run on Render's free plan from `main` ([render.yaml](render.yaml)). Each sleeps after 15
minutes without a visitor and takes about a minute to wake.

> **About this copy.** This repository is Sumanth Varma's working copy of the team's project at
> `ElectricPlant19/GNSS-Constellation-Health-Monitoring-System`. It is publicly readable on GitHub,
> and the hosted dashboard reads its data branches from here without a login. The licences described
> below are in this copy only. The team's repository has none until all four contributors agree
> ([open question](docs/system-design.md#10-open-questions)).

**Contents:** [Using the code](#using-the-code) · [Using the data](#using-the-data) ·
[Citing](#citing) · [Licences](#licences) · [Open questions](#open-questions-for-the-team) ·
[Working in this copy](#working-in-this-copy)

## Using the code

### Install

You need Python 3.11, the version the hosted sites and the test job use ([runtime.txt](runtime.txt)).
The tests also pass on 3.12 locally; the test job runs 3.11 only.

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # requirements.txt plus the test tools
```

### Run the dashboard locally

```bash
streamlit run dashboard.py
```

It opens at <http://localhost:8501>. It needs no login or credentials. It reads the published files
on the data branches (see [Using the data](#using-the-data)) and the bundled orbit history in `data/`.

### Run the other two apps

| App | Command | Needs |
|---|---|---|
| Administration console | `streamlit run admin.py` | A `.streamlit/secrets.toml` laid out like [.streamlit/secrets.example.toml](.streamlit/secrets.example.toml), for Google sign-in, the GitHub token and the rest; without it the console starts but cannot sign anyone in. Questions to its assistant need an Ollama on the same computer, or a DeepSeek key ([system-design, section 8](docs/system-design.md#8-decisions-so-far)). |
| The team's earlier app | `streamlit run app.py` | Nothing, for the bundled data. Fetching fresh history needs a Space-Track.org account. |

Credentials only ever go in a git-ignored `.env` (copy [.env.example](.env.example)), in
`.streamlit/secrets.toml`, or in GitHub Actions secrets. Never commit them.

### Run the tests

```bash
python -m pytest -q
```

The same command runs on every pull request, except one that changes only `README.md`, `registry/README.md`, `CLAUDE.md`, `.lavish/` or `.claude/` ([.github/workflows/tests.yml](.github/workflows/tests.yml)).
One test is marked `coverage_gate` (every broadcasting satellite is tracked or explained): the weekly registry job
skips it so its proposal can show a new satellite, and merging that proposal still needs it ([pytest.ini](pytest.ini)).
The world-map script test is skipped when Node.js is not installed.

### Where the main parts live

| Folder or file | What is in it |
|---|---|
| `dashboard.py`, `views/`, `ui/` | The dashboard: one file per page in `views/` (Home, Overview, Station-keeping, Geometry, News, Master map, World map, Library; the list is `PAGES` in `ui/shell.py`), shared parts, theme and colours in `ui/` |
| `admin.py`, `console/` | The administration console: Summary, System design, Ask, Sources, Jobs, Live pipeline, Alerts, Issues and pull requests, Approvals, Contact inbox (the list is in `console/pages.py`) |
| `analysis/` | The orbit analysis: drift, manoeuvre detection, health scoring, DOP, broadcast orbits, fitted orbits, MEO geometry |
| `config/` | Satellite lists (built from `registry/dashboard_satellites.csv`), slots and the MEO systems' nominal orbits |
| `app.py`, `visualizations/` | The team's earlier app and its plots |
| `api/`, `data/` | Clients for Space-Track.org and CelesTrak, and the bundled orbit history the dashboard starts from |
| `evidence/` | The evidence pipeline: archive, registry tables, news, source grades, confidence labels, alerts |
| `evidence/*_settings.py`, `ui/*_settings.py` | Every setting, each in the file named for who reads it: `evidence/settings.py` for the jobs and the pipeline, the `ui/` ones for the pages |
| `registry/` | Which satellite is which, as plain-text tables ([registry/README.md](registry/README.md)) |
| `scripts/` | What the scheduled jobs run, and tools for building the tables |
| `.github/workflows/` | The scheduled jobs (below) and the test job |
| `cloudflare/newsletters/` | The Cloudflare Worker that serves Substack newsletters as feeds |
| `docs/` | [System design](docs/system-design.md), [evidence model](docs/evidence-model.md), [infrastructure](docs/infrastructure.md), [the team's original notes on the method](docs/method-notes.md) |

### The scheduled jobs

All run on GitHub Actions, only in this repository (each job checks the repository name). GitHub's
clock is UTC, and GitHub often starts scheduled runs hours late: 4 to 6½ hours late in mid-October
2026 ([system-design, section 9](docs/system-design.md#9-assumptions)).

| Job | When (UTC) | What it writes |
|---|---|---|
| `archive.yml` | Per group: documents daily 00:30, catalogues daily 00:45, orbit records every 2 hours from 00:15, news every 3 hours from 00:50, social daily 01:40, X every 6 hours from 00:55, Space-Track launches daily 02:20 | Raw copies to the private archive repository; the `news-data` and `orbit-data` branches |
| `rinex-check.yml` | Daily, 06:00 | The `orbit-checks` branch, and the private archive |
| `update-tle-data.yml` | Sundays 00:00, and whenever `registry/dashboard_satellites.csv` changes on `main` | `data/*.json` on `main`, after the tests pass |
| `registry-update.yml` | Sundays 01:00 | A pull request when the IGS file or GCAT changed the registry tables |
| `source-record.yml` | Sundays 02:00 | A pull request when the source record or grades changed |
| `orbit-ages.yml` | Daily, 03:30 | The private archive only |
| `drills.yml` | By hand only | Nothing real: failure drills on a stand-in site |
| `contact-scan.yml` | No schedule: the console starts it when the contact inbox has an attachment waiting, or by hand | Scans attachments for viruses; an infected one is deleted and its record kept |

Each scheduled run reports to Healthchecks.io, which emails when a run fails or does not arrive.

## Using the data

### Published files on the data branches

Each data branch holds only the files below (`news-data` also has a short `README.md`). The branches are written by the jobs and are never merged
into `main` or deleted. A run that changes nothing makes no commit, so the commit history of each
branch is its record of changes. Read a file directly at:

```
https://raw.githubusercontent.com/SumanthVarma798/GNSS-Constellation-Health-Monitoring-System/<branch>/<file>
```

| Branch | File | Written by | How often | Whose data |
|---|---|---|---|---|
| `orbit-data` | `latest_gnss.json` | `archive.yml`, job `publish-orbits` ([scripts/latest_orbits.py](scripts/latest_orbits.py)) | After each orbit-records run (every 2 hours) that found a change | CelesTrak's |
| `orbit-data` | `home_snapshot.json` | `archive.yml`, job `publish-home` ([scripts/home_snapshot.py](scripts/home_snapshot.py)) | After the orbit copy changes, and otherwise every 8 hours | Ours: Home's counts, made with the dashboard's own code |
| `news-data` | `latest_news.json` | `archive.yml`, job `publish-news` ([scripts/news_items.py](scripts/news_items.py)) | After each news run (every 3 hours) and each X run (every 6 hours) | Headlines and excerpts: their publishers'. Categories and grades: ours |
| `orbit-checks` | `orbit_gap.json` | `rinex-check.yml` ([scripts/orbit_record_gap.py](scripts/orbit_record_gap.py)) | Daily, normally for the day before | Ours, measured against IGS broadcast orbits |
| `orbit-checks` | `fitted_orbits.json` | `rinex-check.yml` | Daily, normally for the day before | Ours: our own fit to IGS broadcast positions, not CelesTrak or Space-Track data |
| `orbit-checks` | `signals_heard.json` | `rinex-check.yml` ([scripts/signals_heard.py](scripts/signals_heard.py)) | Daily, normally for the day before | Ours, measured from six IGS stations' observation files |

"Normally": when the day before's IGS file is not posted yet, the check takes the newest day up to three days
back. The IGS files behind `orbit-checks` come from BKG. When BKG does not give a day's file (it was unreachable on
17 and 18 Nov 2026, and posts the broadcast file about a day late), they come from ESA GSSC's copy of the
same file. `orbit_gap.json` (`broadcast_from`) and `signals_heard.json` (each station's `from`) record which
source served it.

### Formats

All six are JSON. Times are UTC, as ISO 8601; a time with no zone mark (`EPOCH` in an orbit record, `broadcast_newest`) is UTC too. The script that writes each file is the full reference.

| File | Top level | One item |
|---|---|---|
| `latest_gnss.json` | `fetched_at`, `source` (the CelesTrak address), `rows`, `outside_group` | One CelesTrak GP record in its own field names (`OBJECT_NAME`, `NORAD_CAT_ID`, `EPOCH`, `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, ...). `outside_group` holds tracked satellites that CelesTrak's GNSS group leaves out, asked for one by one, kept apart so `rows` is the group as published |
| `latest_news.json` | `generated_at`, `items`, `rules` (the words that put an item in each category), `sources` (each outlet's grade and why) | `title`, `summary`, `outlet`, `address`, `published_at`, `fetched_at`, `constellations`, `category`, `grade`, `grade_standing`, `source_id`, `via` (the feed it came through) |
| `home_snapshot.json` | `made`, `window_days`, `parts` (the counts per constellation), `next_steps`, `next_figures` | (one object; `ui/home_data.py` reads it) |
| `orbit_gap.json` | `day`, `checked`, `satellites`, `broadcast_from` (`BKG` or `ESA GSSC`), `leap_seconds`, `time_corrections` (from the navigation file's header) | Per satellite: `satellite`, `signal_id`, `record_epoch`, `typical_km` and `largest_km` (gap between its orbit record and its broadcast orbit over the day), `mostly` (where the satellite mostly is against its record: ahead on its path or behind, off the record's orbit plane, higher or lower), `fitted_km`, broadcast `health`, `accuracy_m` and `broadcast_newest`, `clock` (how steadily its clock ran), `note` |
| `fitted_orbits.json` | `day`, `checked`, `satellites` | `satellite`, `signal_id`, `norad`, `fit_km` (how closely the fit matches), `row` (the fitted record, in the same fields as a CelesTrak GP record) |
| `signals_heard.json` | `day`, `checked`, `folder`, `sample_every`, `stations` (each: `code`, `name`, `place`, `read`, `megabytes`, `from`) | `satellite`, `signal_id`, `signals` (each signal heard, with the stations that heard it) |

### Data kept in the repository

| Path | What | Updated | Whose data |
|---|---|---|---|
| `registry/*.csv` | Which satellite is which: one row per satellite, signal-ID periods, sightings, the tracked list and why some are left out ([registry/README.md](registry/README.md)) | The built tables (`satellites.csv`, `signal_ids.csv`, `sightings.csv`, `unidentified.csv`) are proposed weekly by `registry-update.yml`; the rest (`constellations.csv`, `dashboard_satellites.csv`, `dashboard_systems.csv`, `left_out.csv`, `clock_record.csv`, `bus_budgets.csv`, `lifecycle_events.csv`, `library_figures.csv`) are kept by a person. A person approves every change | Ours, built from the IGS satellite metadata file, except `catalogue.csv` below |
| `registry/catalogue.csv`, `library_counts.csv`, `library_matching.csv` | Owner and status of each satellite as GCAT states them, and counts made from GCAT | Weekly, with the registry | `catalogue.csv`: GCAT's. The two library tables: ours, counted from GCAT, so they carry GCAT's credit as well as ours ([NOTICE](NOTICE)) |
| `evidence/*.csv` | Source candidates, grades and the checked-claims record | Proposed weekly by `source-record.yml`, or by hand | Ours |
| `data/*_tles.json`, `data/*_gp_history.json` | Latest orbit records and orbit history per system, as `{constellation, timestamp, ..., satellites}` | Weekly by `update-tle-data.yml` | CelesTrak's and Space-Track.org's |
| `ui/figures/land.json` | Land outlines for the maps | A fixed file | Natural Earth (public domain) |

The raw copies behind all of this, and the run logs of the scheduled jobs (all but `update-tle-data.yml`), are in a separate private
repository. They are not published.

## Citing

### The project

Until the team settles the form ([open questions](#open-questions-for-the-team)), cite the project with
the names in [NOTICE](NOTICE), in the order given there:

> Kothandhapani, A., Jhunjhunwala, A., Tiwari, K., Vitrouthu, S. V. and the OpenGNSS contributors
> (2026). *OpenGNSS: GNSS Constellation Health Monitoring System*. <https://dashboard.opengnss.org>

Credit the project's own data, as [NOTICE](NOTICE) asks, as **"data from OpenGNSS (opengnss.org)"**.

### The sources we draw on

Each source keeps its own terms. The middle column is what the source itself states, read on
12 Nov 2026. The last column is the credit this project gives today, in the dashboard footer
(`ui/shell.py`) and [NOTICE](NOTICE). Where a source asks for a citation but gives no wording,
the wording is an open question for the team.

| Source | Used for | What the source states | Credit given today |
|---|---|---|---|
| [Space-Track.org](https://www.space-track.org/documentation#/user_agree) (US Space Command) | Orbit history in `data/*_gp_history.json`; recent launches | Its user agreement bars passing on data received from the site, including analysis of it, without prior express approval. A later section gives blanket approval to redistribute basic data (TLE and OMM orbit records, the satellite catalogue, decay data) on condition of "appropriate citation", and says published analysis also needs citation. It gives no citation wording. | "Orbits from CelesTrak and Space-Track" |
| [CelesTrak](https://celestrak.org/usage-policy.php) | Orbit records: `latest_gnss.json`, `data/*_tles.json` | Its pages make the data freely available. Its usage policy limits how often to download. It states no licence, redistribution limit or credit requirement. | "Orbits from CelesTrak and Space-Track"; on the dashboard, "Orbits from CelesTrak, newest copy from (time)" |
| [International GNSS Service (IGS)](https://igs.org/wp-content/uploads/2020/09/IGS-Data-and-Product-Disclaimer-and-Terms-of-Use-200805.pdf) | The satellite metadata file behind `registry/satellites.csv` and `signal_ids.csv`; the daily broadcast navigation files; six stations' daily observation files | Its Data and Product Disclaimer and Terms of Use (5 Aug 2020) says users agree to cite and attribute IGS resources to their providers and sponsors and acknowledge the IGS and its contributing organisations. It also says IGS data and products should not be used for life-critical functions. The metadata file cites its own format description: Steigenberger P, Montenbruck O (2024), IGS Satellite Metadata File Description, version 1.10, doi:[10.57677/metadata-sinex](https://doi.org/10.57677/metadata-sinex). | "Navigation messages from the IGS, via BKG" |
| [BKG GNSS Data Center](https://igs.bkg.bund.de/) | Where the broadcast navigation and station observation files are downloaded from | Its site states no licence or credit request of its own. It serves the files as an IGS data centre. | Named in "via BKG" |
| [ESA GSSC](https://gssc.esa.int/) (GNSS Science Support Centre) | The same IGS files, on a day BKG does not give them | It serves the IGS files as a data centre, by anonymous FTP. Its terms of use were not read for this README. | Named in `broadcast_from` and each station's `from` in the published files; not in the footer |
| [GCAT](https://planet4589.org/space/gcat/), Jonathan McDowell | `registry/catalogue.csv` and the library tables | Released under CC BY 4.0, free to reproduce as long as it is cited. Short form: "data from GCAT (J. McDowell, planet4589.org/space/gcat)". Full form: McDowell, Jonathan C., 2020. General Catalog of Artificial Space Objects, Release (the release used), https://planet4589.org/space/gcat | "Catalogue from GCAT (J. McDowell, planet4589.org/space/gcat)" |
| [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) | Land outlines on the maps | Public domain. No permission needed and crediting is unnecessary. It offers "Made with Natural Earth." for anyone who wants to credit it. | "Land from Natural Earth" |
| Wikimedia Commons (ISRO pictures) | Pictures on the satellite lifecycle timelines | Shown from Wikimedia Commons, not stored here. Each row of `registry/lifecycle_events.csv` names its picture's credit and licence: five say GODL-India, two say "licence review pending". | The credit in that row, under each picture |
| NASA, via Wikimedia Commons | The console's sign-in picture, `ui/assets/signin-gps-satellite.jpg` | An artist's conception of a GPS Block IIF satellite, `GPS_Satellite_NASA_art-iif.jpg`, described as public domain in pull request 166. Not re-checked against its Commons page. | "Artist's conception of a GPS Block II-F satellite. NASA, public domain.", on the sign-in card |
| News publishers, and posts on X and Reddit | `latest_news.json` | Each headline and excerpt belongs to its publisher. Each item keeps its outlet and address. | The outlet and a link, on every item |
| The team's MEO app, `ElectricPlant19/Static_MEO_GNSS_Monitor` | Two diagnostics on the MEO pages, not scored: along-track rate, and tilt against the other satellites in its plane | That app has no licence, so nothing is copied from it. The two diagnostics follow how that app shows them, written afresh in `analysis/meo_geometry.py` and `ui/meo_overview.py`, which credit it. | "as the team's static MEO app (ElectricPlant19/Static_MEO_GNSS_Monitor) shows them", on the MEO pages |

## Licences

| What | Licence | File |
|---|---|---|
| The source code | Apache License 2.0 | [LICENSE](LICENSE) |
| The data the project makes itself: `registry/*.csv` except `registry/catalogue.csv` (the two library tables, counted from GCAT, also carry GCAT's credit), `evidence/*.csv`, and the files our own jobs publish (`orbit_gap.json`, `fitted_orbits.json`, `signals_heard.json`, `home_snapshot.json`) | Creative Commons Attribution 4.0 International (CC BY 4.0) | [LICENSE-DATA](LICENSE-DATA) |
| Everything from others (the table above) | Its owner's terms. Neither licence above applies to it | [NOTICE](NOTICE) lists which files are which |

Copyright 2026 Adithya Kothandhapani, Aditya Jhunjhunwala, Krishi Tiwari, Sumanth Varma Vitrouthu and
the OpenGNSS contributors.

**What Apache-2.0 means for the code.** Anyone may use, change and pass on the code, for any purpose,
including commercially (section 2). In return, a copy passed on must carry the licence, keep the
copyright and attribution notices and the [NOTICE](NOTICE) file, and mark the files that were changed
(section 4). So the project's credit stays attached to every copy. Each contributor grants a patent licence
for their contributions, and that licence ends for anyone who sues claiming the code infringes a patent
(section 3). It gives no right to use the project's names or marks, beyond saying where the code came
from (section 6). The code comes with no warranty, and the contributors are not liable for its use
(sections 7 and 8). A contribution made to this repository is under the same licence unless its author
says otherwise (section 5).

**What CC BY 4.0 means for our data.** Anyone may copy, share and adapt the data, for any purpose,
including commercially (section 2). It covers database rights as well as copyright (section 4). In
return, anyone who shares it must credit the project, link to the licence and say whether they changed it
(section 3). They may not add terms or technical measures that stop others doing the same (section
2(a)(5)). The rights end automatically on a breach and come back if it is put right within 30 days of
finding out (section 6). The data comes with no warranty (section 5). It grants no patent or trademark
rights (section 2(b)).

Neither licence lets anyone pass off others' data as ours, or as covered by our terms: Space-Track,
CelesTrak, IGS, BKG, ESA GSSC, GCAT, Natural Earth and news data keep their owners' terms.

## Open questions for the team

These could not be settled from the sources' own terms or from the repository. They are for the team
to decide together. The licence question itself is in
[system-design, section 10](docs/system-design.md#10-open-questions).

| Topic | Question |
|---|---|
| Space-Track | Its user agreement bars passing on data without prior express approval, but its section on basic data gives blanket approval for orbit records on condition of appropriate citation. Does that approval cover keeping Space-Track orbit history in this public repository (`data/*_gp_history.json`)? |
| Space-Track | It asks for "appropriate citation" but gives no wording. What wording do we use, and where do we show it? |
| CelesTrak | It states no credit terms. Is "CelesTrak" enough, or should the credit also name where CelesTrak's records come from? |
| IGS | Its terms ask users to cite and attribute to providers and sponsors, but give no wording in the parts we could read. Its documents page has a Citation tab we could not read. Which wording do we use? Should it name the data centre (BKG, or ESA GSSC on the days it serves the files)? |
| News | `latest_news.json` is public and carries each item's headline and an excerpt of up to about 300 characters. Is that the right amount to publish? |
| Pictures | `NOTICE` lists neither the lifecycle pictures nor the console's sign-in picture. Should it? And may the two lifecycle pictures marked "licence review pending" be shown before Commons settles their licence? |
| Citing the project | Which author order, and which address: the team's repository, this copy or `opengnss.org`? Once the licences are agreed, should we add a `CITATION.cff` (so GitHub shows "Cite this repository") and a DOI, for example from Zenodo? |

## Working in this copy

- **Remotes:** `origin` is this copy. `upstream` is the team's repository and is fetch-only: its push
  address is set to `DISABLED`. After a fresh clone, run `git remote set-url --push upstream DISABLED`
  before anything else.
- **Syncing:** `git fetch upstream`, then merge `upstream/main` into `main` through a pull request.
- **Line endings:** some files use Windows (CRLF) endings and some Unix (LF). Keep each file as it is;
  check with `git ls-files --eol` before editing.
- **Design:** [docs/system-design.md](docs/system-design.md) is the one page on what is planned, built
  and assumed. A pull request that changes behaviour updates it.
- **Console access:** sign in at <https://console.opengnss.org> with a Google account on the console's
  list; ask Sumanth to be added.
- **Domain and hosting:** `opengnss.org` and how each part is hosted and renewed:
  [docs/infrastructure.md](docs/infrastructure.md).

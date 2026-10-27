# Satellite registry

Which satellite is which. `satellites.csv` and `signal_ids.csv` are built from the
International GNSS Service (IGS) satellite metadata file by `scripts/build_registry.py`.
**Do not edit those two by hand**: a change arrives as a pull request that a person reviews.

    python scripts/build_registry.py
    git diff registry/        # the change report; empty means nothing changed at the source

| File | Kept by | What it holds |
|---|---|---|
| `satellites.csv` | the build script | One row per physical satellite |
| `signal_ids.csv` | the build script | One row per satellite per signal-ID period |
| `constellations.csv` | a person | Which system each SVN letter stands for |
| `catalogue.csv` | its own build script | Owner and status of each satellite, as a second source states them |
| `dashboard_satellites.csv` | a person | Which satellites the dashboard tracks, and its name for each |

Code reads and writes these tables through `evidence/registry_tables.py`; file names
and column names are written down once, in `evidence/settings.py`.

## satellites.csv: one row per physical satellite

| Column | Meaning |
|---|---|
| `svn` | Space vehicle number, one per physical satellite. The key for everything else. |
| `constellation` | GPS, GLONASS, Galileo, BeiDou, QZSS or NavIC. |
| `block` | The satellite's design generation, as the IGS file names it. |
| `cospar_id` | International launch designator. |
| `catalogue_no` | Catalogue number (NORAD ID), the key used by orbit data. |
| `signal_id_now` | The signal ID (PRN) the IGS file assigns to it today. Blank if none. An assignment is not proof that it is broadcasting. |
| `plane`, `slot` | Where it sits today, as the IGS file states it. Blank if not given. |
| `note` | The IGS file's comment, usually launch date and name. |

## signal_ids.csv: one row per satellite per signal-ID period

| Column | Meaning |
|---|---|
| `svn` | The satellite. |
| `signal_id` | The signal ID (PRN) assigned to it in this period. |
| `valid_from`, `valid_to` | Start and end in UTC. A blank end means it still holds. |
| `note` | The IGS file's comment, often the operator's notice number. |

A signal ID can pass from one satellite to another, so join signal data on the
signal ID **and** the time, never on the signal ID alone.

## constellations.csv: one row per navigation system

| Column | Meaning |
|---|---|
| `svn_letter` | The first letter of every SVN in that system. |
| `constellation` | The system's name as shown to readers. |

If the IGS file ever lists a system whose letter is not here, the build stops and
says so. A person adds the row after looking.

## catalogue.csv: one row per satellite, from a second source

Built by `scripts/build_catalogue_table.py` from the General Catalog of Artificial Space
Objects (GCAT) by Jonathan McDowell, matched to `satellites.csv` by catalogue number.
**Do not edit by hand.** Values are kept exactly as the catalogue writes them. The
catalogue is released under CC-BY: wherever its data is shown, cite it as
"data from GCAT (J. McDowell, planet4589.org/space/gcat)".

| Column | Meaning |
|---|---|
| `svn` | The satellite. |
| `cospar_id` | International launch designator, as the catalogue gives it. Compare with the one in `satellites.csv`. |
| `name` | The catalogue's name for the payload. |
| `owner`, `state` | The catalogue's codes for the owner or operator, and for its country or organisation. |
| `status` | The catalogue's status code. `O` is in orbit. `N` means its name or owner changed on some date and the later record is kept elsewhere in the catalogue. |
| `orbit_class` | The kind of orbit early in its working life, not necessarily today's. |
| `last_known_active` | When the catalogue's author last knew it to be active. He says he updates this patchily. |
| `operations_ended` | When regular operations ended. `*` means it is believed to be still operating. |
| `mission_result` | `S` success, `F` failed early, `U` unknown. |

A row of blanks means the catalogue does not list that satellite yet. The two sources are
kept by different people, so they are never guaranteed to be in step.

    python scripts/build_catalogue_table.py --archive FOLDER --report DISAGREEMENTS.md

The report lists where this table and `satellites.csv` disagree, and picks no winner.

## dashboard_satellites.csv: one row per satellite the dashboard tracks

| Column | Meaning |
|---|---|
| `svn` | The satellite. Its catalogue number and constellation are looked up in `satellites.csv`. |
| `dashboard_name` | The name the dashboard shows. Orbit data, service requirements and recorded scores are all keyed by it, so changing one is a change to the dashboard, not a correction. |
| `added` | When this satellite was added to the tracked list (`YYYY-MM-DD`, UTC). Left blank for rows that predate this record. |

Row order is the order the dashboard shows them in. `config/config.py` builds its three
satellite lists from this table. Adding a satellite here is the team's decision.

**Adding or removing a row can move other satellites' scores**, even when the new satellite
has no orbit data: the dashboard takes the size of a constellation to be the number of
rows here. The recorded-score tests fail on any proposal that moves a score, so a proposal
to add or remove a satellite must say which scores move, and re-record them on approval.

This table and `satellites.csv` are each approved by a person, at different times. If a
row names an SVN that `satellites.csv` does not have, the dashboard runs without that
satellite and shows a notice naming it. A test fails on any proposal that would cause it.

## What these tables do not say

Whether a satellite is providing a navigation service. The IGS file does not carry that,
and the catalogue's "still operating" is not the same thing: a satellite can be operated
without providing one.

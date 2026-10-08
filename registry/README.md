# Satellite registry

Which satellite is which. Built from the International GNSS Service (IGS) satellite
metadata file by `scripts/build_registry.py`. **Do not edit these files by hand**: a
change arrives as a pull request that a person reviews.

    python scripts/build_registry.py
    git diff registry/        # the change report; empty means nothing changed at the source

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

## What these tables do not say

Whether a satellite is healthy or in service. The IGS file does not carry that.

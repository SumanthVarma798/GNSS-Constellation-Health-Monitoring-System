# Burn record: what the team is asked to confirm

The constellation score now has a fourth measure, the **burn record** ("care" in the code). It is built on the kind of each
burn (`analysis/burn_classes.py`, settings in `analysis/burn_class_settings.py`). Every number below is our choice, not a
standard. Home, each constellation's Overview and Station-keeping show it; the per-satellite Overall Score does not read it.

## 1. How it enters the score (ui/limits.py)

- Weight 10% for every constellation, taken evenly from the other three. Regional (NavIC, QZSS): clock 45%, station 27%,
  orbit 18%, burn record 10%. Global: clock 36%, orbit 31.5%, station 22.5%, burn record 10%.
  Is 10% the right size, and is "taken evenly" right?
- A satellite passes when it has no irregular burn (a response or an off-pattern burn, at medium confidence or better) in
  the last 90 days AND at most 25% of its judged burns in 365 days are irregular.
- Not judged with fewer than 3 judged burns in 365 days. New satellites still moving to their slot and set-aside
  satellites are skipped. A constellation with no burn history (the medium-orbit ones) has no burn record: the other three
  count for 100%, so its score is unchanged.
- Relocations and end-of-life burns count for neither side (neutral). Is that right for a relocation made in answer to a problem?
- The constellation line "3 of 41 burns irregular (7%, 2–20%)" is over the same 365 days, with a 95% Wilson interval;
  under 8 judged burns it says "too few to rate".

## 2. Thresholds in analysis/burn_class_settings.py

Please confirm or change each group: the context windows (2 days before and after a burn, drift noise 0.005 °/day);
the artefact limits (east-west above 20 m/s, tilt step above 1°, undone within 90 days to within 25%);
relocation (19 km each burn, 0.25 °/day between, 2 to 400 days, 5° moved); end of life (45-day raise sequence);
routine (3 own earlier burns or 3 peers, interval margin 25%, size 0.5 to 2 times the norm, north-south gap 40 days);
response (3 burns in 7 days, a reversal within 3 days, drift limit 0.05 °/day); and the summary (365-day window,
8 judged burns to rate, medium confidence counts, 95% interval).

## 3. Why the health table's burn count differs from the burn list

The burn list (`burns()`, what Station-keeping and the burn record read) uses every day of each satellite's history. The
health table's pattern analysis keeps only the days on which at least 75% of the constellation's satellites have records
(`analysis/bundled_run.py`, `min_required`), so its burn counts can be lower. Which should the score's burn record use?

## 4. Real burns to check by hand (label as of 18 Nov 2026)

Each line: satellite, date (UTC), size change, our label and confidence. Does each label match what the operator did?

1. BeiDou-3 G1, 4 Apr 2026, −106.6 km: relocation, high (pair with 16 Apr, drift +1.36 °/day between)
2. BeiDou-3 G1, 16 Apr 2026, +107.0 km: relocation, high (the other half of the pair)
3. BeiDou-3 G1, 27 to 29 Jul 2026, four east-west burns in three days (−6.7, +5.2, +11.7, −4.5 km): response, high; plus a
   north-south burn on 27 Jul: routine north-south, medium
4. BeiDou-3 G1, 14 May 2026, +1.86 km with a −0.197° tilt step: unexplained (east-west) and routine north-south, both low
5. BeiDou-3 G2, 5 Dec 2025 (−0.50° tilt): routine north-south, medium; and 18 Aug 2026 (−0.45°): routine north-south, medium
6. BeiDou-3 I3, 30 Dec 2025, tilt step +3.87° (208 m/s): artefact, high (left out as a record error); 8 Feb 2026 also artefact
7. NVS-01, 11 Dec 2025 to 3 Nov 2026, 15 east-west burns every 3 to 4 weeks: all routine east-west (the first low, then medium, then high)
8. IRNSS-1G, 3 to 11 Dec 2025, four burns in nine days: response, high
9. IRNSS-1G, 19 to 26 Jun 2026, three burns in a week (+1.9, −5.0, −1.6 km): response, high
10. IRNSS-1G, 14 to 15 Oct 2026, three burns in two days (+5.1, +5.0, −2.9 km): response, high
11. IRNSS-1G, 24 Aug and 29 Oct 2026: off-cycle timing, medium (only the interval is off; not counted)
12. IRNSS-1G, 16 Sep 2026, −4.6 km: routine east-west, high, between two clusters
13. QZS-1R, 1 Feb and 4 Aug 2026, about −16 km each: routine east-west, low (not counted: too few of its own earlier burns)

IRNSS-1G is the only NavIC satellite that does not pass (11 of 17 judged burns irregular). BeiDou-3 shows 3 satellites with
a judged burn record; QZSS 2 of 2 pass.

## 5. Questions that stay open for the team

- Is a burn "found within the days between two records" precise enough to call a response or an off-pattern burn,
  without the operator's own manoeuvre log?
- Should a cluster of burns after a planned relocation count as a response?
- Are CelesTrak and Space-Track records enough for the medium-orbit constellations, or should the burn record stay blank for them?

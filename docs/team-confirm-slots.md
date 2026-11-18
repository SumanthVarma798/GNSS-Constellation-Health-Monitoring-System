# Slots to confirm

Written for Adithya, Aditya and Krishi. The dashboard judges each satellite against the longitude in our slot table.
Two satellites have been kept, steadily and for 90 days or more, a long way from that longitude. The likelier reading is
that the table is out of date, not that the satellites are off their slots, so the dashboard now says "slot to confirm"
and works out their next burn about the place they are kept (ui/next_step.py; the rule's numbers are in
ui/next_step_settings.py: 90 days, at least 80 % of records within a box of the station).

Where the table lives: `config/config.py`, `NAVIK_SERVICE_REQUIREMENTS` (NavIC), `QZSS_SERVICE_REQUIREMENTS` (QZSS) and
`BEIDOU3_SERVICE_REQUIREMENTS` (BeiDou-3). We have not changed it. Station is the median mean longitude over the last
90 days, from the element sets (read 18 Nov 2026).

| Satellite | Station | Slot in our table | Kept from the table | To confirm |
|---|---|---|---|---|
| NVS-01 | 129.5° E | 131.5° E | 2.0° west | ISRO placed NVS-01 at 129.5° E, which is IRNSS-1G's longitude in our table: is 131.5° E right? |
| QZS-1R (Michibiki-1R) | 134.9° E | 148° E | 13.1° west | Which position did QZS-1R take over, and is 148° E (QZS-1's old slot) still the one to judge it against? |

The rule found no other satellite of NavIC, QZSS or BeiDou-3. The next largest are BeiDou-2 IGSO-6 (2.5° east of its
slot, inside its 5° box) and QZS-4 (1.2° east, inside its 5° box).

What changes when a slot is confirmed or corrected: edit the table, and the satellite is judged against it again (its
score, "in slot" state and the longitude measures also read the table).

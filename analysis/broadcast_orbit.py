"""Where a navigation satellite is, from the orbit it broadcasts (a RINEX 3 navigation file).

Every navigation satellite broadcasts its own orbit as a set of numbers (its ephemeris),
good to metres, so receivers can work out position. GPS, Galileo, BeiDou, QZSS and NavIC
use one formula (IS-GPS-200, table 20-IV) with their own constants; BeiDou's geostationary
satellites add one rotation (BeiDou ICD, section 5.2.4.12). GLONASS broadcasts a position and
velocity instead; its positions are not handled here, only its health and record time are read.

Nothing here downloads or reads the clock. Positions are Earth-fixed, in km.
"""
import math
from datetime import datetime, timedelta

# System letter -> (gravitational constant m^3/s^2, Earth's rotation rad/s, from each system's interface document.
SYSTEMS = {
    "G": (3.986005e14, 7.2921151467e-5),     # GPS
    "J": (3.986005e14, 7.2921151467e-5),     # QZSS, as GPS
    "I": (3.986005e14, 7.2921151467e-5),     # NavIC, as GPS
    "E": (3.986004418e14, 7.2921151467e-5),  # Galileo
    "C": (3.986004418e14, 7.292115e-5),      # BeiDou (CGCS2000)
}
BEIDOU_GEO = {f"C{n:02d}" for n in [*range(1, 6), *range(59, 64)]}   # signal IDs of BeiDou's geostationary satellites
BEIDOU_BEHIND_GPS = 14       # seconds: BeiDou time started 14 s after GPS time and has no leap seconds
GEO_TILT = math.radians(-5)  # the BeiDou geostationary rotation
FIT = 4 * 3600               # seconds either side of a record's reference time it is used for


def _number(field):
    field = field.strip().replace("D", "E")
    return float(field) if field else 0.0


def read_navigation(text):
    """{signal ID: [record, ...]} for the systems in SYSTEMS, from a RINEX 3 navigation file's text.

    A record is a dict: "toc" (a naive datetime in the satellite's own time), the 3 clock terms,
    and the broadcast orbit values by name. Records of other systems (GLONASS, SBAS) are skipped.
    """
    lines = text.splitlines()
    body = lines[next(i for i, line in enumerate(lines) if "END OF HEADER" in line) + 1:]
    starts = [i for i, line in enumerate(body) if line[:1].strip()]
    records = {}
    for start, end in zip(starts, [*starts[1:], len(body)]):
        first = body[start]
        if first[0] not in SYSTEMS:
            continue
        values = [_number(first[c:c + 19]) for c in (23, 42, 61)]
        for line in body[start + 1:end]:
            values += [_number(line[c:c + 19]) for c in (4, 23, 42, 61)]
        year, month, day, hour, minute, second = (int(x) for x in first[4:23].split())
        record = dict(zip(_NAMES, values), toc=datetime(year, month, day, hour, minute, second), id=first[:3])
        records.setdefault(first[:3], []).append(record)
    return records


_NAMES = ["af0", "af1", "af2",
          "iode", "crs", "delta_n", "m0",
          "cuc", "e", "cus", "sqrt_a",
          "toe", "cic", "omega0", "cis",
          "i0", "crc", "omega", "omega_dot",
          "idot", "codes", "week", "l2p",
          "accuracy", "health", "tgd", "iodc",
          "sent", "fit"]


def _toc(first):
    """The satellite's own time (a naive datetime) from a record's first line."""
    year, month, day, hour, minute, second = (int(x) for x in first[4:23].split())
    return datetime(year, month, day, hour, minute, second)


def _known(field):
    """A field's number, or None when it is blank (RINEX's "not known")."""
    return _number(field) if field.strip() else None


def _records_from_lines(lines):
    """Raw records for every system from the navigation body, including GLONASS."""
    body = lines[next(i for i, line in enumerate(lines) if "END OF HEADER" in line) + 1:]
    starts = [i for i, line in enumerate(body) if line[:1].strip()]
    records = {}
    for start, end in zip(starts, [*starts[1:], len(body)]):
        first = body[start]
        if first[0] not in "GECJIR":
            continue
        signal_id = first[:3]
        toc = _toc(first)
        if first[0] == "R":
            health = _known(body[start + 1][61:80])
            records.setdefault(signal_id, []).append(
                {"toc": toc, "health": None if health is None else int(health), "accuracy": None, "iode": None})
            continue
        fields = [first[c:c + 19] for c in (23, 42, 61)]
        for line in body[start + 1:end]:
            fields += [line[c:c + 19] for c in (4, 23, 42, 61)]
        record = {name: _known(field) for name, field in zip(_NAMES, fields)}
        health, accuracy, iode = record.get("health"), record.get("accuracy"), record.get("iode")
        records.setdefault(signal_id, []).append(
            {"toc": toc, "health": None if health is None else int(health),
             # Galileo sends -1 for "no accuracy prediction available"
             "accuracy": accuracy if accuracy is not None and accuracy >= 0 else None,
             "iode": None if iode is None else int(iode)})
    return records


def read_status(text):
    """{signal ID: {"health", "accuracy_m", "iod", "newest"}} from a RINEX 3 navigation file's text.

    G, E, C, J and I use the fields read_navigation already reads; GLONASS records carry only a health
    value. Newest means the record with the latest toc (the satellite's own time); where several records
    share that toc, the largest health wins.
    """
    lines = text.splitlines()
    out = {}
    for signal_id, records in _records_from_lines(lines).items():
        newest = max(records, key=lambda record: record["toc"])
        tied = [record for record in records if record["toc"] == newest["toc"]]
        chosen = max(tied, key=lambda record: -1 if record["health"] is None else record["health"])
        out[signal_id] = {"health": chosen["health"], "accuracy_m": chosen["accuracy"],
                          "iod": chosen["iode"], "newest": chosen["toc"]}
    return out


def time_corrections(text):
    """{code: a0 in seconds} from the header's TIME SYSTEM CORR lines."""
    out = {}
    for line in text.splitlines():
        if "TIME SYSTEM CORR" in line:
            out[line[:4].strip()] = _number(line[5:22])
    return out


def system_time(utc, signal_id, leap_seconds):
    """The satellite system's own clock reading at `utc` (naive datetimes)."""
    ahead = leap_seconds - (BEIDOU_BEHIND_GPS if signal_id[0] == "C" else 0)
    return utc + timedelta(seconds=ahead)


def seconds_from_toe(record, when):
    """Seconds from the record's reference time (toe) to `when`, both in the satellite's own time."""
    sunday = (record["toc"] - timedelta(days=(record["toc"].weekday() + 1) % 7)).replace(hour=0, minute=0, second=0)
    toe = sunday + timedelta(seconds=record["toe"])
    if (toe - record["toc"]).total_seconds() > 302400:      # the week rolled over between toe and toc
        toe -= timedelta(weeks=1)
    elif (record["toc"] - toe).total_seconds() > 302400:
        toe += timedelta(weeks=1)
    return (when - toe).total_seconds()


def nearest(records, when):
    """The record whose reference time is closest to `when` (the satellite's own time)."""
    return min(records, key=lambda record: abs(seconds_from_toe(record, when)))


def position(record, when):
    """Earth-fixed (x, y, z) in km at `when`, a naive datetime in the satellite's own time."""
    gm, spin = SYSTEMS[record["id"][0]]
    tk = seconds_from_toe(record, when)
    a = record["sqrt_a"] ** 2
    mean_anomaly = record["m0"] + (math.sqrt(gm / a ** 3) + record["delta_n"]) * tk
    eccentric = mean_anomaly
    for _ in range(12):                                     # Kepler's equation; e is below 0.01 here
        eccentric = mean_anomaly + record["e"] * math.sin(eccentric)
    e = record["e"]
    true_anomaly = math.atan2(math.sqrt(1 - e * e) * math.sin(eccentric), math.cos(eccentric) - e)
    phi = true_anomaly + record["omega"]
    sin2, cos2 = math.sin(2 * phi), math.cos(2 * phi)
    u = phi + record["cus"] * sin2 + record["cuc"] * cos2
    r = a * (1 - e * math.cos(eccentric)) + record["crs"] * sin2 + record["crc"] * cos2
    incl = record["i0"] + record["idot"] * tk + record["cis"] * sin2 + record["cic"] * cos2
    x_plane, y_plane = r * math.cos(u), r * math.sin(u)

    geo = record["id"] in BEIDOU_GEO
    node = record["omega0"] + (record["omega_dot"] - (0 if geo else spin)) * tk - spin * record["toe"]
    x = x_plane * math.cos(node) - y_plane * math.cos(incl) * math.sin(node)
    y = x_plane * math.sin(node) + y_plane * math.cos(incl) * math.cos(node)
    z = y_plane * math.sin(incl)
    if geo:                                                 # tilt by -5 degrees about x, then turn with the Earth
        y, z = math.cos(GEO_TILT) * y + math.sin(GEO_TILT) * z, -math.sin(GEO_TILT) * y + math.cos(GEO_TILT) * z
        turn = spin * tk
        x, y = math.cos(turn) * x + math.sin(turn) * y, -math.sin(turn) * x + math.cos(turn) * y
    return x / 1000, y / 1000, z / 1000

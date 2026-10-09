-- The evidence model: source -> document -> claim -> event.
--
-- This file is the one description of the model. The query store is a SQLite
-- file built from it on every run (see evidence/store.py) and thrown away
-- after, so nothing here is edited by hand in a database. The types and
-- constraints are kept plain so the same file can serve Postgres later.
--
-- STORAGE RULE: this store holds references and a few small details, never a
-- document itself. A document row carries the hash that names its raw copy in
-- the archive. No column here may hold a page's or a file's content.

-- ---------------------------------------------------------------- Who is who

CREATE TABLE constellation (
    svn_letter  TEXT PRIMARY KEY,           -- first letter of every SVN in the system
    name        TEXT NOT NULL UNIQUE
);

CREATE TABLE satellite (
    svn            TEXT PRIMARY KEY,        -- space vehicle number: one per physical satellite
    constellation  TEXT NOT NULL REFERENCES constellation (name),
    block          TEXT NOT NULL,
    cospar_id      TEXT NOT NULL,
    catalogue_no   INTEGER NOT NULL,        -- the key used by orbit data
    signal_id_now  TEXT,                    -- NULL when none is assigned
    plane          TEXT,
    slot           TEXT,
    note           TEXT
);

CREATE TABLE signal_id_period (
    svn         TEXT NOT NULL REFERENCES satellite (svn),
    signal_id   TEXT NOT NULL,
    valid_from  TEXT NOT NULL,              -- UTC, ISO 8601
    valid_to    TEXT,                       -- NULL while it still holds
    note        TEXT,
    PRIMARY KEY (svn, valid_from)
);

-- ------------------------------------------------------------- The evidence

-- Who published something. The reliability grade (A to F) belongs to the
-- source, and stays NULL until a person has graded it.
CREATE TABLE source (
    id           TEXT PRIMARY KEY,          -- the host name the source publishes from
    name         TEXT NOT NULL,
    reliability  TEXT CHECK (reliability IN ('A', 'B', 'C', 'D', 'E', 'F'))
);

-- One dated raw copy from a source, or the record that the page was gone.
-- A REFERENCE ONLY: the copy itself is in the archive, named by its hash.
CREATE TABLE document (
    id            INTEGER PRIMARY KEY,      -- its row number in the archive's change log, so it never changes
    source_id     TEXT NOT NULL REFERENCES source (id),
    address       TEXT NOT NULL,
    fetched_at    TEXT NOT NULL,            -- UTC, ISO 8601
    status        INTEGER NOT NULL,         -- 200 for a copy; 404 or 410 when the page was gone
    sha256        TEXT,                     -- names the raw copy in the archive; NULL when the page was gone
    bytes         INTEGER NOT NULL,
    content_type  TEXT,
    wayback_url   TEXT,                     -- the Internet Archive's own dated copy, when there is one
    CHECK ((sha256 IS NULL) = (status <> 200))
);

-- One statement taken from one document. The credibility grade (1 to 6)
-- belongs to the statement, and stays NULL until it has been graded.
CREATE TABLE claim (
    id           INTEGER PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES document (id),
    svn          TEXT REFERENCES satellite (svn),   -- NULL when it is about no single satellite
    statement    TEXT NOT NULL,
    credibility  INTEGER CHECK (credibility BETWEEN 1 AND 6)
);

-- Something that happened to a satellite.
CREATE TABLE event (
    id           INTEGER PRIMARY KEY,
    svn          TEXT NOT NULL REFERENCES satellite (svn),
    happened_on  TEXT,                      -- UTC date, when known
    summary      TEXT NOT NULL
);

-- A claim either supports an event or contests it. Two sources that disagree
-- both stay on record, attached to the same event.
CREATE TABLE event_claim (
    event_id  INTEGER NOT NULL REFERENCES event (id),
    claim_id  INTEGER NOT NULL REFERENCES claim (id),
    stance    TEXT NOT NULL CHECK (stance IN ('supports', 'contests')),
    PRIMARY KEY (event_id, claim_id)
);

-- Something we measured ourselves. Not a claim: nobody said it. An event may
-- stand on observation alone ("the operator said nothing, but we saw a burn").
CREATE TABLE observation (
    id           INTEGER PRIMARY KEY,
    event_id     INTEGER NOT NULL REFERENCES event (id),
    kind         TEXT NOT NULL CHECK (kind IN ('orbit', 'signal')),
    observed_at  TEXT NOT NULL,             -- UTC, ISO 8601
    summary      TEXT NOT NULL
);

CREATE TABLE event_tag (
    event_id  INTEGER NOT NULL REFERENCES event (id),
    tag       TEXT NOT NULL,
    PRIMARY KEY (event_id, tag)
);

-- "Last updated" for a satellite is worked out, never stored: the newest
-- document behind any claim attached to any of its events.
CREATE VIEW satellite_last_updated AS
SELECT event.svn AS svn, MAX(document.fetched_at) AS last_updated
FROM event
JOIN event_claim ON event_claim.event_id = event.id
JOIN claim ON claim.id = event_claim.claim_id
JOIN document ON document.id = claim.document_id
GROUP BY event.svn;

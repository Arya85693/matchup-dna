"""Storage for the forecasting engine: one SQLite file, standard library only.

The schema is plain SQL with primary keys, foreign keys, unique constraints and indexes, so it can move to
PostgreSQL unchanged in substance when a hosted database is justified (brief, section 39). SQLite is enough for one
writer and a periodically updated site, and adds no dependency or server.

What cannot be changed once written

    predictions             a forecast, its inputs and its model version: no UPDATE, no DELETE (database triggers)
    outcomes                each result as a source reported it: append-only; disagreements are flagged, never
                            overwritten
    source_records          every provider record ever received, with its retrieval and ingestion times
    eligibility_decisions   why each model did or did not forecast each match in each run
    identity_observations   which canonical player each provider id resolved to in each run
    model_versions          the frozen model artifacts, by hash

A new forecast for the same match and model is a new row that names the row it supersedes; the earlier one stays.
Re-running a job with the same inputs writes nothing new (unique on match, model and input hash).

Every prediction is also chained: record_hash = sha256(previous record_hash + prediction_id), in insertion order.
`export_ledger` writes the chain as JSON lines (forecasts/ledger.jsonl), so a committed copy of the ledger is
outside evidence that no earlier forecast was changed or removed. `verify` recomputes every hash.

A store is created in one of two modes, fixed for its life: "live" holds genuine forecasts issued before matches;
"replay" holds simulated forecasts for past matches (pipeline rehearsals) and can never be mixed with live ones.
"""
import datetime
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from matchup_dna.forecasting.records import UTC, canonical_json, iso, sha256_text

SCHEMA_VERSION = "1"
MODES = ("live", "replay")
GENESIS = "0" * 64

APPEND_ONLY = ("predictions", "outcomes", "source_records", "eligibility_decisions", "identity_observations",
               "model_versions", "editions", "edition_aliases", "matches", "match_aliases", "match_observations")

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,                 -- ingest, forecast, settle, evaluate
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,               -- running, ok, failed
    as_of TEXT NOT NULL,                -- the moment the run treats as "now"
    code_commit TEXT,
    inputs_json TEXT NOT NULL,          -- file hashes, snapshot hashes, settings
    counts_json TEXT
);

CREATE TABLE IF NOT EXISTS source_records (
    record_id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    tour TEXT NOT NULL,
    provider_match_id TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,       -- the record without its retrieval time
    status TEXT NOT NULL,
    event_time TEXT,
    published_at TEXT,
    retrieved_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    payload_json TEXT NOT NULL,
    UNIQUE (provider, tour, provider_match_id, content_sha256)
);
CREATE INDEX IF NOT EXISTS source_records_match ON source_records (provider, tour, provider_match_id);

CREATE TABLE IF NOT EXISTS editions (
    edition_uid TEXT PRIMARY KEY,
    tour TEXT NOT NULL,
    name TEXT NOT NULL,
    tourney_date INTEGER NOT NULL,      -- YYYYMMDD, the edition's first main-draw day
    level TEXT,
    surface TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edition_aliases (
    provider TEXT NOT NULL,
    provider_edition_key TEXT NOT NULL,
    edition_uid TEXT NOT NULL REFERENCES editions(edition_uid),
    created_at TEXT NOT NULL,
    PRIMARY KEY (provider, provider_edition_key)
);

CREATE TABLE IF NOT EXISTS matches (
    match_uid TEXT PRIMARY KEY,
    tour TEXT NOT NULL,
    edition_uid TEXT NOT NULL REFERENCES editions(edition_uid),
    round TEXT NOT NULL,
    player_low INTEGER NOT NULL,        -- canonical ids, ordered, so the key never depends on a side or result
    player_high INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tour, edition_uid, round, player_low, player_high),
    CHECK (player_low < player_high)
);

CREATE TABLE IF NOT EXISTS match_aliases (
    provider TEXT NOT NULL,
    tour TEXT NOT NULL,
    provider_match_id TEXT NOT NULL,
    match_uid TEXT NOT NULL REFERENCES matches(match_uid),
    created_at TEXT NOT NULL,
    PRIMARY KEY (provider, tour, provider_match_id)
);

CREATE TABLE IF NOT EXISTS match_observations (
    match_uid TEXT NOT NULL REFERENCES matches(match_uid),
    record_id INTEGER NOT NULL REFERENCES source_records(record_id),
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    PRIMARY KEY (match_uid, record_id)
);

CREATE TABLE IF NOT EXISTS identity_observations (
    provider TEXT NOT NULL,
    tour TEXT NOT NULL,
    provider_player_id TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    player_id INTEGER NOT NULL,
    status TEXT NOT NULL,               -- verified, new_player, ambiguous, conflict
    method TEXT NOT NULL,
    first_run_id TEXT NOT NULL REFERENCES runs(run_id),
    first_seen_at TEXT NOT NULL,
    UNIQUE (provider, tour, provider_player_id, player_id, status, method)
);

CREATE TABLE IF NOT EXISTS model_versions (
    model_version TEXT PRIMARY KEY,
    kind TEXT NOT NULL,                 -- tournament_start, round_aware
    artifact_sha256 TEXT NOT NULL UNIQUE,
    artifact_json TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT NOT NULL UNIQUE, -- sha256 of the canonical content below
    match_uid TEXT NOT NULL REFERENCES matches(match_uid),
    model_version TEXT NOT NULL REFERENCES model_versions(model_version),
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    issued_at TEXT NOT NULL,
    scheduled_start TEXT,               -- as known when issued
    player_a INTEGER NOT NULL,          -- the probability is for player A; A is chosen without any result
    player_b INTEGER NOT NULL,
    p_a REAL NOT NULL CHECK (p_a > 0 AND p_a < 1),
    input_sha256 TEXT NOT NULL,
    content_json TEXT NOT NULL,         -- everything hashed into prediction_id, including the input snapshot
    supersedes TEXT,                    -- the prediction_id this one replaces for the same match and model, if any
    prev_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    UNIQUE (match_uid, model_version, input_sha256)
);
CREATE INDEX IF NOT EXISTS predictions_match ON predictions (match_uid, model_version, seq);

CREATE TABLE IF NOT EXISTS eligibility_decisions (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    match_uid TEXT NOT NULL REFERENCES matches(match_uid),
    model_version TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    decision TEXT NOT NULL,             -- issued, unchanged, ineligible, deferred, too_late
    reason TEXT NOT NULL,
    prediction_id TEXT,
    PRIMARY KEY (run_id, match_uid, model_version)
);

CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id INTEGER PRIMARY KEY,
    match_uid TEXT NOT NULL REFERENCES matches(match_uid),
    source TEXT NOT NULL,               -- tml, tennisdata_app, ...
    provider_match_id TEXT,
    status TEXT NOT NULL,               -- completed, retired, walkover, cancelled
    winner_id INTEGER,
    score TEXT,
    best_of INTEGER,
    retrieved_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    UNIQUE (match_uid, source, status, winner_id, score)
);
"""


def _append_only_triggers(table):
    return (f"CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;\n"
            f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;\n")


def now_utc():
    return datetime.datetime.now(UTC)


class StoreError(RuntimeError):
    pass


class Store:
    def __init__(self, path, mode=None):
        """Opens or creates the store at `path`. A new store needs a mode; an existing one must match it."""
        self.path = Path(path)
        new = str(path) == ":memory:" or not self.path.exists()
        if new and mode not in MODES:
            raise StoreError(f"a new store needs a mode, one of {MODES}")
        if new and str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), isolation_level=None)
        try:
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA foreign_keys = ON")
            self.db.executescript(SCHEMA + "".join(_append_only_triggers(t) for t in APPEND_ONLY))
            stored = self.info("mode")
            if stored is None:
                if mode not in MODES:
                    raise StoreError(f"{path} has no mode; open it with one of {MODES}")
                self.db.execute("INSERT INTO schema_info VALUES ('mode', ?), ('schema_version', ?), ('created_at', ?)",
                                (mode, SCHEMA_VERSION, iso(now_utc())))
            elif mode is not None and mode != stored:
                raise StoreError(f"{path} is a {stored} store; it cannot be opened as {mode}")
        except BaseException:
            self.db.close()
            raise
        self.mode = self.info("mode")

    def close(self):
        self.db.close()

    def __del__(self):
        db = getattr(self, "db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    def info(self, key):
        row = self.db.execute("SELECT value FROM schema_info WHERE key = ?", (key,)).fetchone()
        return None if row is None else row["value"]

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    # ------------------------------------------------------------ runs

    def start_run(self, run_id, kind, as_of, inputs, code_commit=None):
        self.db.execute("INSERT INTO runs (run_id, kind, started_at, status, as_of, code_commit, inputs_json) "
                        "VALUES (?, ?, ?, 'running', ?, ?, ?)",
                        (run_id, kind, iso(now_utc()), iso(as_of), code_commit, canonical_json(inputs)))

    def finish_run(self, run_id, status, counts):
        self.db.execute("UPDATE runs SET finished_at = ?, status = ?, counts_json = ? WHERE run_id = ?",
                        (iso(now_utc()), status, canonical_json(counts), run_id))

    def runs(self, kind=None):
        query = "SELECT * FROM runs" + (" WHERE kind = ?" if kind else "") + " ORDER BY started_at"
        return [dict(r) for r in self.db.execute(query, (kind,) if kind else ())]

    # ------------------------------------------------------------ source records

    def add_source_record(self, record, run_id, ingested_at):
        """Stores a provider record unless an identical one (same content) is already stored. Returns
        (record_id, new)."""
        content = record.content_sha256()
        found = self.db.execute("SELECT record_id FROM source_records WHERE provider = ? AND tour = ? AND "
                                "provider_match_id = ? AND content_sha256 = ?",
                                (record.provider, record.tour, record.provider_match_id, content)).fetchone()
        if found:
            return found["record_id"], False
        cursor = self.db.execute(
            "INSERT INTO source_records (provider, tour, provider_match_id, content_sha256, status, event_time, "
            "published_at, retrieved_at, ingested_at, run_id, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record.provider, record.tour, record.provider_match_id, content, record.status, record.event_time,
             record.published_at, record.retrieved_at, iso(ingested_at), run_id, canonical_json(record.payload())))
        return cursor.lastrowid, True

    # ------------------------------------------------------------ canonical identities

    def ensure_edition(self, edition_uid, tour, name, tourney_date, level, surface, created_at):
        self.db.execute("INSERT INTO editions VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                        (edition_uid, tour, name, tourney_date, level, surface, iso(created_at)))

    def edition_for_alias(self, provider, key):
        row = self.db.execute("SELECT edition_uid FROM edition_aliases WHERE provider = ? AND provider_edition_key = ?",
                              (provider, key)).fetchone()
        return None if row is None else row["edition_uid"]

    def add_edition_alias(self, provider, key, edition_uid, created_at):
        existing = self.edition_for_alias(provider, key)
        if existing is not None and existing != edition_uid:
            raise StoreError(f"edition alias {provider}:{key} already points to {existing}, not {edition_uid}")
        self.db.execute("INSERT INTO edition_aliases VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                        (provider, key, edition_uid, iso(created_at)))

    def match_for_alias(self, provider, tour, provider_match_id):
        row = self.db.execute("SELECT match_uid FROM match_aliases WHERE provider = ? AND tour = ? AND "
                              "provider_match_id = ?", (provider, tour, provider_match_id)).fetchone()
        return None if row is None else row["match_uid"]

    def match(self, match_uid):
        row = self.db.execute("SELECT * FROM matches WHERE match_uid = ?", (match_uid,)).fetchone()
        return None if row is None else dict(row)

    def match_by_key(self, tour, edition_uid, round_name, low, high):
        row = self.db.execute("SELECT * FROM matches WHERE tour = ? AND edition_uid = ? AND round = ? AND "
                              "player_low = ? AND player_high = ?", (tour, edition_uid, round_name, low, high)).fetchone()
        return None if row is None else dict(row)

    def ensure_match(self, match_uid, tour, edition_uid, round_name, low, high, created_at):
        if low >= high:
            raise StoreError("player_low must be below player_high")
        existing = self.match_by_key(tour, edition_uid, round_name, low, high)
        if existing is not None:
            if existing["match_uid"] != match_uid:
                raise StoreError(f"match key already stored as {existing['match_uid']}")
            return False
        self.db.execute("INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (match_uid, tour, edition_uid, round_name, low, high, iso(created_at)))
        return True

    def add_match_alias(self, provider, tour, provider_match_id, match_uid, created_at):
        existing = self.match_for_alias(provider, tour, provider_match_id)
        if existing is not None and existing != match_uid:
            raise StoreError(f"{provider} match {tour}/{provider_match_id} is already {existing}, not {match_uid}")
        self.db.execute("INSERT INTO match_aliases VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                        (provider, tour, provider_match_id, match_uid, iso(created_at)))

    def add_match_observation(self, match_uid, record_id, run_id):
        self.db.execute("INSERT INTO match_observations VALUES (?, ?, ?) ON CONFLICT DO NOTHING", (match_uid, record_id, run_id))

    def observe_identity(self, provider, tour, provider_player_id, name, player_id, status, method, run_id, seen_at):
        self.db.execute("INSERT INTO identity_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                        (provider, tour, str(provider_player_id), name, player_id, status, method, run_id, iso(seen_at)))

    def identity_drift(self):
        """Provider ids that have resolved to more than one canonical player across runs."""
        rows = self.db.execute(
            "SELECT provider, tour, provider_player_id, COUNT(DISTINCT player_id) AS ids, "
            "GROUP_CONCAT(DISTINCT player_id) AS players FROM identity_observations "
            "GROUP BY provider, tour, provider_player_id HAVING ids > 1").fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ models

    def register_model(self, model_version, kind, artifact_text, artifact_sha256):
        row = self.db.execute("SELECT artifact_sha256 FROM model_versions WHERE model_version = ?",
                              (model_version,)).fetchone()
        if row is not None:
            if row["artifact_sha256"] != artifact_sha256:
                raise StoreError(f"model version {model_version} is already registered with a different artifact; "
                                 "a changed model needs a new version name")
            return False
        self.db.execute("INSERT INTO model_versions VALUES (?, ?, ?, ?, ?)",
                        (model_version, kind, artifact_sha256, artifact_text, iso(now_utc())))
        return True

    def model_sha(self, model_version):
        row = self.db.execute("SELECT artifact_sha256 FROM model_versions WHERE model_version = ?",
                              (model_version,)).fetchone()
        return None if row is None else row["artifact_sha256"]

    # ------------------------------------------------------------ predictions

    def last_hash(self):
        row = self.db.execute("SELECT record_hash FROM predictions ORDER BY seq DESC LIMIT 1").fetchone()
        return GENESIS if row is None else row["record_hash"]

    def latest_prediction(self, match_uid, model_version):
        row = self.db.execute("SELECT * FROM predictions WHERE match_uid = ? AND model_version = ? "
                              "ORDER BY seq DESC LIMIT 1", (match_uid, model_version)).fetchone()
        return None if row is None else dict(row)

    def add_prediction(self, content):
        """Stores one prediction. `content` is the full canonical record (see pipeline.prediction_content). Returns
        ("unchanged", existing id) if a prediction with the same match, model and inputs exists, else
        ("issued", new id). The caller holds the transaction."""
        for field in ("match_uid", "model_version", "run_id", "issued_at", "player_a", "player_b", "p_a",
                      "input_sha256", "inputs"):
            if field not in content:
                raise StoreError(f"prediction content lacks {field}")
        if content["model_sha256"] != self.model_sha(content["model_version"]):
            raise StoreError(f"model {content['model_version']} is not registered with artifact {content['model_sha256']}")
        same = self.db.execute("SELECT prediction_id FROM predictions WHERE match_uid = ? AND model_version = ? "
                               "AND input_sha256 = ?", (content["match_uid"], content["model_version"],
                                                        content["input_sha256"])).fetchone()
        if same is not None:
            return "unchanged", same["prediction_id"]
        previous = self.latest_prediction(content["match_uid"], content["model_version"])
        content = dict(content, supersedes=None if previous is None else previous["prediction_id"])
        text = canonical_json(content)
        prediction_id = sha256_text(text)
        prev_hash = self.last_hash()
        record_hash = sha256_text(prev_hash + prediction_id)
        self.db.execute(
            "INSERT INTO predictions (prediction_id, match_uid, model_version, run_id, issued_at, scheduled_start, "
            "player_a, player_b, p_a, input_sha256, content_json, supersedes, prev_hash, record_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (prediction_id, content["match_uid"], content["model_version"], content["run_id"], content["issued_at"],
             content.get("scheduled_start"), content["player_a"], content["player_b"], content["p_a"],
             content["input_sha256"], text, content["supersedes"], prev_hash, record_hash))
        return "issued", prediction_id

    def predictions(self, model_version=None):
        query = "SELECT * FROM predictions" + (" WHERE model_version = ?" if model_version else "") + " ORDER BY seq"
        return [dict(r) for r in self.db.execute(query, (model_version,) if model_version else ())]

    def add_decision(self, run_id, match_uid, model_version, decided_at, decision, reason, prediction_id=None):
        self.db.execute("INSERT INTO eligibility_decisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (run_id, match_uid, model_version, iso(decided_at), decision, reason, prediction_id))

    def decisions(self, run_id=None):
        query = "SELECT * FROM eligibility_decisions" + (" WHERE run_id = ?" if run_id else "")
        return [dict(r) for r in self.db.execute(query, (run_id,) if run_id else ())]

    # ------------------------------------------------------------ outcomes

    def add_outcome(self, match_uid, source, provider_match_id, status, winner_id, score, best_of, retrieved_at,
                    recorded_at, run_id):
        """Stores one source's report of a result, unless the same report is stored. Returns True if new. A report
        without a retrieval time is refused: it could not be shown to have been known before it was used."""
        if retrieved_at is None:
            raise StoreError(f"{source} result for {match_uid} has no retrieval time")
        same = self.db.execute("SELECT 1 FROM outcomes WHERE match_uid = ? AND source = ? AND status = ? AND "
                               "winner_id IS ? AND score IS ?", (match_uid, source, status, winner_id, score)).fetchone()
        if same:
            return False
        cursor = self.db.execute(
            "INSERT INTO outcomes (match_uid, source, provider_match_id, status, winner_id, score, best_of, "
            "retrieved_at, recorded_at, run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (match_uid, source, provider_match_id, status, winner_id, score, best_of, iso(retrieved_at),
             iso(recorded_at), run_id))
        return cursor.rowcount == 1

    def outcomes(self, match_uid=None):
        query = "SELECT * FROM outcomes" + (" WHERE match_uid = ?" if match_uid else "") + " ORDER BY outcome_id"
        return [dict(r) for r in self.db.execute(query, (match_uid,) if match_uid else ())]

    def settled(self):
        """{match_uid: settlement}. A match is settled when every stored outcome agrees on status and winner;
        otherwise its settlement is a conflict, and it is left out of evaluation until a person resolves it."""
        found = {}
        for row in self.outcomes():
            entry = found.setdefault(row["match_uid"], {"rows": []})
            entry["rows"].append(row)
        for match_uid, entry in found.items():
            pairs = {(r["status"], r["winner_id"]) for r in entry["rows"]}
            if len(pairs) == 1:
                status, winner = pairs.pop()
                entry.update(state="settled", status=status, winner_id=winner,
                             settled_at=min(r["recorded_at"] for r in entry["rows"]))
            else:
                entry.update(state="conflict", status=None, winner_id=None, settled_at=None)
        return found

    # ------------------------------------------------------------ integrity

    def verify(self):
        """Recomputes every prediction id and chain hash. Returns a list of problems (empty if intact)."""
        problems, previous = [], GENESIS
        for row in self.db.execute("SELECT * FROM predictions ORDER BY seq"):
            content = json.loads(row["content_json"])
            if sha256_text(canonical_json(content)) != row["prediction_id"]:
                problems.append(f"seq {row['seq']}: content does not hash to its prediction_id")
            if row["prev_hash"] != previous:
                problems.append(f"seq {row['seq']}: chain broken (prev_hash)")
            if sha256_text(previous + row["prediction_id"]) != row["record_hash"]:
                problems.append(f"seq {row['seq']}: record_hash wrong")
            for column in ("match_uid", "model_version", "issued_at", "player_a", "player_b", "p_a", "input_sha256"):
                if content[column] != row[column]:
                    problems.append(f"seq {row['seq']}: column {column} differs from its hashed content")
            previous = row["record_hash"]
        return problems

    def export_ledger(self, path):
        """Writes every prediction, in chain order, as JSON lines. An existing ledger must be a prefix of the new one
        (nothing earlier may differ), so a committed ledger cannot be silently rewritten."""
        path = Path(path)
        lines = [canonical_json({"seq": r["seq"], "prediction_id": r["prediction_id"], "prev_hash": r["prev_hash"],
                                 "record_hash": r["record_hash"], "content": json.loads(r["content_json"])})
                 for r in self.db.execute("SELECT * FROM predictions ORDER BY seq")]
        if path.exists():
            old = path.read_text(encoding="utf-8").splitlines()
            if old != lines[:len(old)]:
                raise StoreError(f"{path} is not a prefix of this store's chain: an earlier forecast differs or is "
                                 "missing. Nothing was written.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
        return len(lines)

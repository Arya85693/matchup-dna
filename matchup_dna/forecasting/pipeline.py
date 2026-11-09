"""The production jobs: ingest a snapshot, forecast pending fixtures, settle finished matches.

    forecast(store, sources, models, as_of)    one run: provider records stored with their times; history and
                                               fixtures assembled; canonical editions and matches recorded; every
                                               (fixture, model) decided and, if eligible, forecast and stored
    settle(store, sources, as_of)              results attached to stored matches, never to their predictions

Both are idempotent. Re-running with the same data writes no new prediction, outcome, record, edition or match: the
store's unique keys make every insert a no-op when the content is already there. A forecast whose inputs changed
(for example a corrected result in a player's history) is stored as a new prediction that names the one it
supersedes; the earlier one is kept and stays the one the prospective evaluation scores.

`replay_sources(sources, day)` cuts the provider rows at the start of a past day, as if the snapshot had been taken
then: rows dated before the day keep their results, that day's TD rows become scheduled fixtures, and later rows are
dropped. A replay run writes only to a store created in "replay" mode. It is a rehearsal, never a forecast record.
"""
import copy
import datetime
import json
import subprocess
from collections import Counter

from matchup_dna.elo import RESULTS_DIR
from matchup_dna.forecasting import engine
from matchup_dna.forecasting.frozen_models import load_models
from matchup_dna.forecasting.history import TD_PROVIDER, apply_reviews, assemble, load_identity_reviews
from matchup_dna.forecasting.records import FINAL_STATUSES, UTC, canonical_json, iso, sha256_text, utc
from matchup_dna.heldout import ymd

ROOT = RESULTS_DIR.parent
LIVE_CLOCK_TOLERANCE = datetime.timedelta(minutes=5)
STORED_RECORDS_BACK = datetime.timedelta(days=21)    # provider records stored per run: those near the run's time
STORED_RECORDS_AHEAD = datetime.timedelta(days=7)
PROFILE_SETTINGS = RESULTS_DIR / "phase4" / "profile_settings.json"
IDENTITY_REVIEWS = ROOT / "forecasts" / "identity_reviews.csv"
LEDGER = ROOT / "forecasts" / "ledger.jsonl"


def code_commit():
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT,
                                check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "matchup_dna", "models"], capture_output=True,
                               text=True, cwd=ROOT, check=True).stdout.strip()
        return commit + ("+uncommitted" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_id(kind, as_of):
    return f"{kind}-{utc(as_of).strftime('%Y%m%dT%H%M%SZ')}-{sha256_text(iso(datetime.datetime.now(UTC)) + kind)[:6]}"


def file_hashes(paths):
    from matchup_dna.experiment import sha256
    return {path.name: sha256(path) for path in paths}


def source_inputs(sources):
    """Hashes of the provider files and profile settings a run read (empty where a file is absent, as in tests)."""
    from matchup_dna import tennisdata as td
    from matchup_dna import tennisismylife as tml
    try:
        files = file_hashes(list(tml.tml_files()) + list(td.provider_files()))
    except (FileNotFoundError, ValueError):
        files = {}
    return {"files": files, "retrieved_at": sources.retrieved_at,
            "profile_settings": file_hashes([PROFILE_SETTINGS]) if PROFILE_SETTINGS.exists() else {}}


# ---------------------------------------------------------------- canonical records in the store

def record_edition(store, fixture, at):
    store.ensure_edition(fixture["edition_uid"], fixture["tour"], fixture["tourney_name"], fixture["tourney_date"],
                         fixture["tourney_level"], fixture["surface"], at)
    for provider, key in fixture["edition_aliases"]:
        store.add_edition_alias(provider, key, fixture["edition_uid"], at)


def record_match(store, fixture, at):
    """The canonical match for a fixture. A provider match id seen before keeps its match: if the players now
    resolve differently, that is an identity change, and the fixture is not forecast (returns None)."""
    uid = engine.fixture_uid(fixture)
    known = store.match_for_alias(fixture["provider"], fixture["tour"], fixture["provider_match_id"])
    if known is not None and known != uid:
        return None
    low, high = sorted((fixture["home"]["player_id"], fixture["away"]["player_id"]))
    store.ensure_match(uid, fixture["tour"], fixture["edition_uid"], fixture["round"], low, high, at)
    store.add_match_alias(fixture["provider"], fixture["tour"], fixture["provider_match_id"], uid, at)
    return uid


# ---------------------------------------------------------------- the assembly a live run uses

ESPN_EVIDENCE_FROM = datetime.date(2025, 1, 1)
IDENTITY_ALIASES = ROOT / "forecasts" / "identity_aliases.csv"
ESPN_REFRESH_DAYS_BACK = 14
ESPN_REFRESH_DAYS_AHEAD = 3


def refresh_espn(today, directory=None):
    """Archives ESPN scoreboards for the last ESPN_REFRESH_DAYS_BACK days and the next ESPN_REFRESH_DAYS_AHEAD days
    (results that finished since the last run, fixtures as they are published). Returns the number of requests."""
    from matchup_dna.forecasting import espn
    first = today - datetime.timedelta(days=ESPN_REFRESH_DAYS_BACK)
    return espn.sync(first, today + datetime.timedelta(days=ESPN_REFRESH_DAYS_AHEAD), directory, refresh_from=first)


def live_assembly(sources, as_of, use_espn=True, directory=None):
    """The history and fixtures as of `as_of`: the file snapshots, plus (by default) every ESPN response archived at
    or before `as_of`, which adds results the files lack and supplies the fixtures."""
    assembly = assemble(sources)
    if use_espn:
        from matchup_dna.forecasting import espn
        records = espn.load_archive(directory, since=ESPN_EVIDENCE_FROM, as_of=as_of)
        espn.integrate(assembly, sources, records, evidence_since=int(ESPN_EVIDENCE_FROM.strftime("%Y%m%d")),
                       aliases=espn.load_aliases(IDENTITY_ALIASES))
    return assembly


# ---------------------------------------------------------------- forecast

def forecast(store, sources, as_of, models=None, assembly=None, tml_rows=None, td_rows=None, settings=PROFILE_SETTINGS,
             reviews_path=IDENTITY_REVIEWS, ledger_path=None, commit=None):
    """One forecast run at `as_of` (the issue time). Returns (run id, counts)."""
    as_of = utc(as_of)
    if store.mode == "live" and abs(as_of - datetime.datetime.now(UTC)) > LIVE_CLOCK_TOLERANCE:
        raise ValueError("a live forecast is issued now: a past or future issue time is a replay, which belongs in a "
                         "replay store")
    from matchup_dna.forecasting.prospective import code_sha256
    models = models or load_models()
    commit = commit or code_commit()
    code_sha = code_sha256()
    rid = run_id("forecast", as_of)
    store.start_run(rid, "forecast", as_of, {**source_inputs(sources), "code_sha256": code_sha,
                                             "models": {m.version: m.sha256 for m in models.values()}}, commit)
    counts = Counter()
    try:
        assembly = assembly or assemble(sources, tml_rows=tml_rows, td_rows=td_rows)
        fixtures = apply_reviews(assembly.fixtures, load_identity_reviews(reviews_path))
        history_info = {"sha256": engine.history_digest(assembly.matches), "matches": len(assembly.matches),
                        "through_day": max(m["match_day"] for m in assembly.matches),
                        "retrieved_at": sources.retrieved_at}
        with store.transaction():
            for model in models.values():
                store.register_model(model.version, model.kind, model.text, model.sha256)
            record_ids = {}
            low, high = as_of - STORED_RECORDS_BACK, as_of + STORED_RECORDS_AHEAD
            for record in assembly.records:
                when = utc(record.event_time) if record.event_time else None
                if when is None and record.extra.get("listed_date"):
                    when = utc(record.extra["listed_date"] + "T00:00:00Z")
                if when is not None and not low <= when <= high:
                    continue   # older records are evidence for linking, not inputs to these forecasts
                record_id, new = store.add_source_record(record, rid, as_of)
                record_ids[record.key] = record_id
                counts["provider records new" if new else "provider records already stored"] += 1
            for fixture in fixtures:
                for side in ("home", "away"):
                    person = fixture[side]
                    store.observe_identity(fixture["provider"], fixture["tour"], person["provider_id"], person["name"],
                                           person["player_id"], person["status"], person["method"], rid, as_of)

        candidates, uids = [], {}
        with store.transaction():
            for fixture in fixtures:
                if fixture["status"] == "duplicate":
                    counts["fixtures: duplicate listings (not recorded)"] += 1
                    continue
                if fixture["home"]["player_id"] == fixture["away"]["player_id"]:
                    counts["fixtures: both sides the same player (not recorded)"] += 1
                    continue
                record_edition(store, fixture, as_of)
                uid = record_match(store, fixture, as_of)
                if uid is None:
                    counts["fixtures: identity changed since first seen (not forecast)"] += 1
                    continue
                uids[id(fixture)] = uid
                record_id = record_ids.get((fixture["provider"], fixture["tour"], fixture["provider_match_id"]))
                if record_id is not None:
                    store.add_match_observation(uid, record_id, rid)
                if engine.common_checks(fixture, as_of, assembly) is None:
                    candidates.append(fixture)

        rows = engine.fixture_rows(assembly.matches, candidates, settings) if candidates else {}
        with store.transaction():
            for fixture in fixtures:
                uid = uids.get(id(fixture))
                if uid is None:
                    continue
                row = rows.get(uid)
                for kind in engine.KIND_ORDER:
                    model = models[kind]
                    decision, reason = engine.decide(fixture, row, model, as_of, assembly)
                    prediction_id = None
                    if decision == "issued":
                        content = engine.prediction_content(uid, fixture, row, model, as_of, rid, store.mode,
                                                            history_info, commit, code_sha)
                        decision, prediction_id = store.add_prediction(content)
                    store.add_decision(rid, uid, model.version, as_of, decision, reason, prediction_id)
                    counts[f"{kind}: {decision}"] += 1
        counts.update({f"assembly: {k}": v for k, v in assembly.report.items() if isinstance(v, int)})
        store.finish_run(rid, "ok", dict(counts))
    except BaseException:
        store.finish_run(rid, "failed", dict(counts))
        raise
    if ledger_path is not None:
        store.export_ledger(ledger_path)
    return rid, dict(counts)


# ---------------------------------------------------------------- settle

OUTCOME_STATUS = {"completed": "completed", "retired": "retired", "walkover": "walkover", "default": "retired",
                  "abandoned": "cancelled", "unknown": "unknown"}


def settle(store, sources, as_of, assembly=None, tml_rows=None, td_rows=None, commit=None):
    """Attaches every available result to stored matches. A result comes from the canonical history (the TML row,
    or the TD row when TML lacks the match) and, separately, from the TD row with the fixture's own provider id.
    Each source's report is a separate outcome row; if they disagree, the match is a conflict and is not scored."""
    as_of = utc(as_of)
    rid = run_id("settle", as_of)
    store.start_run(rid, "settle", as_of, source_inputs(sources), commit or code_commit())
    counts = Counter()
    try:
        assembly = assembly or assemble(sources, tml_rows=tml_rows, td_rows=td_rows)
        canonical = {}
        for m in assembly.matches:
            if m["tourney_date"] >= 20260601:
                canonical[(m["tour"], m["tourney_id"], m["round"], frozenset((m["winner_id"], m["loser_id"])))] = m
        records = {r.key: r for r in assembly.records}
        with store.transaction():
            settled = store.settled()
            for match in [dict(r) for r in store.db.execute("SELECT * FROM matches")]:
                if match["match_uid"] in settled and settled[match["match_uid"]]["state"] == "settled":
                    counts["already settled"] += 1
                    continue
                pair = frozenset((match["player_low"], match["player_high"]))
                tourney_ids = set()
                for alias in store.db.execute("SELECT * FROM edition_aliases WHERE edition_uid = ?",
                                              (match["edition_uid"],)):
                    tourney_ids |= assembly.alias_tourney_ids.get((alias["provider"], alias["provider_edition_key"]),
                                                                  set())
                found = False
                for tourney_id in tourney_ids:
                    m = canonical.get((match["tour"], tourney_id, match["round"], pair))
                    if m is not None and m["source"] == "tml":
                        status = OUTCOME_STATUS.get(m["outcome"], "unknown")
                        store.add_outcome(match["match_uid"], "tml", m["match_num"], status, m["winner_id"],
                                          m["score"], m["best_of"], sources.retrieved_at.get(m.get("source_file")),
                                          as_of, rid)
                        found = True
                for alias in store.db.execute("SELECT * FROM match_aliases WHERE match_uid = ?", (match["match_uid"],)):
                    record = records.get((alias["provider"], alias["tour"], alias["provider_match_id"]))
                    if record is None or record.status not in FINAL_STATUSES:
                        continue
                    winner = None
                    if record.winner_side:
                        resolve = assembly.resolvers.get(alias["provider"])
                        if resolve is None:
                            counts[f"no identity resolver for {alias['provider']} (not stored)"] += 1
                            continue
                        winner = resolve(record.tour, getattr(record, f"{record.winner_side}_id"),
                                         getattr(record, f"{record.winner_side}_name"))["player_id"]
                        if winner not in pair:
                            counts["winner is not one of the stored players (identity mismatch; not stored)"] += 1
                            continue
                    store.add_outcome(match["match_uid"], alias["provider"], record.provider_match_id, record.status,
                                      winner, record.score, record.best_of, record.retrieved_at, as_of, rid)
                    found = True
                counts["matches with a result" if found else "matches without a result yet"] += 1
        counts["conflicting results"] = sum(1 for s in store.settled().values() if s["state"] == "conflict")
        store.finish_run(rid, "ok", dict(counts))
    except BaseException:
        store.finish_run(rid, "failed", dict(counts))
        raise
    return rid, dict(counts)


# ---------------------------------------------------------------- replay (rehearsal on past days)

TD_RESULT_COLUMNS = ("winner_code", "home_set_score", "away_set_score") + tuple(
    f"{side}_set_{n}_score" for side in ("home", "away") for n in range(1, 6))


UNLINKED_TML_DELAY = datetime.timedelta(days=2)


def tml_known_days(sources):
    """{id(TML row): the day its result became known}. TML dates each 2026 round by its first day, and a round can
    span two or three days, so the round date would let a replay see results not yet played. A TML row linked to a
    TD row takes the TD row's UTC match day; an unlinked one takes its round date plus UNLINKED_TML_DELAY.
    Computed once per Sources (the linking uses names, ids, rounds and dates, never results)."""
    cached = getattr(sources, "_tml_known_days", None)
    if cached is not None:
        return cached
    from matchup_dna import tennisdata as td
    from matchup_dna.audit_tennisismylife import tml_day
    from matchup_dna.forecasting.history import PROVIDER_START, is_pending, window
    from matchup_dna.heldout import link_rows
    tml_window, td_window, _, td_editions = window(sources.tml_rows, sources.td_rows, sources.excluded, PROVIDER_START)
    pairs, _, _, _, _ = link_rows([r for r in td_window if not is_pending(r)], tml_window, sources.td_links,
                                  sources.tml_links, td_editions)
    known = {id(row): tml_day(row) + UNLINKED_TML_DELAY for row in sources.tml_rows}
    for td_row, tml_row, _ in pairs:
        known[id(tml_row)] = td_row["day"]
    sources._tml_known_days = known
    return known


def replay_sources(sources, day):
    """(TML rows, TD rows) as a snapshot taken at 00:00 UTC on `day` would have held them: results known before the
    day (tml_known_days), that day's TD main-draw rows as scheduled fixtures (results removed), nothing later. A TML
    edition with a row not yet known counts as ongoing."""
    known = tml_known_days(sources)
    tml_rows, ongoing = [], set()
    for row in sources.tml_rows:
        if known[id(row)] >= day:
            ongoing.add((row["tour"], row["tourney_id"]))
    for row in sources.tml_rows:
        if known[id(row)] < day:
            copy_row = dict(row)
            copy_row["ongoing"] = copy_row["ongoing"] or (row["tour"], row["tourney_id"]) in ongoing
            tml_rows.append(copy_row)
    td_rows = []
    for row in sources.td_rows:
        if row["day"] < day:
            td_rows.append(row)
        elif row["day"] == day:
            fixture = copy.copy(row)
            fixture["status"], fixture["status_extra"] = "SCHEDULED", "SCHEDULED"
            for column in TD_RESULT_COLUMNS:
                if column in fixture:
                    fixture[column] = ""
            td_rows.append(fixture)
    return tml_rows, td_rows

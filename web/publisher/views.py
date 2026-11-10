"""The website's public views of a forecast store.

Every probability, contribution, input and timestamp is a stored value; nothing here forecasts or refits. The track
record is computed with the Phase 6 protocol's own functions (`prospective.counted_predictions`, `outcome_rows`,
`metrics`, `paired`) and the same selection as `prospective.evaluate`, so the site can never count a forecast the
protocol would not. Fields are allowlisted: run ids, provider ids, file paths and raw provider payloads never leave.

    match_index(store, now)         pending matches (with or without a start time) and results from the last week
    match_page(store, uid, now)     everything public about one match: every forecast version, decisions, results
    track_record(store, now)        the prospective record P1, labelled interim
    models_view(store)              model versions and what each uses
    status_view(store, now)         freshness, counts and the integrity check
    ledger_recent(store)            the latest entries of the hash-chained forecast ledger

Pilot exceptions (web/content/pilot_exceptions.json): a pilot forecast the project owner chose to show on a match's
Results row and match page. It is read unchanged from the published pilot ledger, must have been issued before the
match started, for the same two players, by a model version the store knows, and is marked `pilot`. It never enters
`snap.predictions`, so the counted set, track record, archive and player views cannot include it.
"""
import datetime
import json
import math
from collections import defaultdict
from pathlib import Path

from matchup_dna.forecasting import api, prospective
from matchup_dna.forecasting.records import iso, utc
from web.publisher import reasons

SCHEMA_VERSION = "1"
KINDS = ("tournament_start", "round_aware")
RESULT_DAYS = 7               # results stay on the Match Center for a week
EDITION_DAYS = 21             # an unsettled match from an edition older than this is not "upcoming"
LEDGER_RECENT = 200
ROOT = Path(__file__).resolve().parents[2]
PILOT_EXCEPTIONS = ROOT / "web" / "content" / "pilot_exceptions.json"

PLAYER_INPUTS = {             # public name: stored row field (without the a_/b_ prefix)
    "elo": "elo", "surface_elo": "surface_elo_blended", "elo_matches": "elo_matches",
    "surface_matches": "surface_matches", "rank": "rank", "days_since_last_match": "days_since", "form": "form",
    "form_matches": "form_matches", "serve_points_won": "serve_adjusted", "return_points_won": "return_adjusted",
}
ROUND_AWARE_INPUTS = {
    "matches_this_event": "ra_matches", "games_won_share_this_event": "ra_games_won_share",
    "elo_change_this_event": "ra_elo_shift", "surface_elo_change_this_event": "ra_surface_elo_shift",
}


# ---------------------------------------------------------------- helpers

def _clean(value):
    """JSON-safe: numpy scalars to Python, NaN and infinities to None."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _date(yyyymmdd):
    s = str(yyyymmdd)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _edition_start(yyyymmdd):
    s = str(yyyymmdd)
    return datetime.datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=datetime.timezone.utc)


def counted(store, protocol):
    """{(match_uid, model_version): prediction row} counted under the P1 protocol, exactly as prospective.evaluate
    selects them: the first stored forecast in the window at least 30 minutes before the start, scheduled up to the
    window's end, issued by the protocol's code and models."""
    window = protocol["window"]
    chosen = prospective.counted_predictions(store, window["issued_from"], None, "first")
    end = utc(window["scheduled_up_to"])
    models = {m["artifact_sha256"] for m in protocol["models"].values()}
    return {k: v for k, v in chosen.items()
            if utc(v["scheduled_start"]) <= end and v["content"].get("code_sha256") == protocol["code_sha256"]
            and v["content"]["model_sha256"] in models}


def load_pilots(matches, records, kinds, path=PILOT_EXCEPTIONS, root=ROOT):
    """{(match_uid, model_version): [pilot row]} for the approved exceptions that pass every check; a failing one is
    skipped with a message, never shown."""
    if not Path(path).exists():
        return {}
    found = {}
    for ex in json.loads(Path(path).read_text(encoding="utf-8"))["matches"]:
        uid, wanted = ex["match_uid"], ex["prediction_id"]
        line = None
        for text in (Path(root) / ex["ledger"]).read_text(encoding="utf-8").splitlines():
            entry = json.loads(text) if text.strip() else None
            if entry and entry["prediction_id"] == wanted:
                line = entry
        match, record = matches.get(uid), records.get(uid) or {}
        content = (line or {}).get("content", {})
        start = record.get("event_time")
        problem = (None if line else "not in its ledger") or (None if match else "unknown match") or (
            None if {content.get("player_a"), content.get("player_b")} == {match["player_low"], match["player_high"]}
            else "different players") or (None if content.get("model_version") in kinds else "unknown model version") or (
            None if start and content.get("issued_at", "9") < start else "not issued before the match started")
        if problem:
            print(f"pilot exception {wanted[:12]} for {uid} skipped: {problem}")
            continue
        found[(uid, content["model_version"])] = [{
            "prediction_id": wanted, "match_uid": uid, "model_version": content["model_version"],
            "player_a": content["player_a"], "player_b": content["player_b"], "p_a": content["p_a"],
            "issued_at": content["issued_at"], "scheduled_start": content.get("scheduled_start"),
            "supersedes": content.get("supersedes"), "input_sha256": content["input_sha256"],
            "record_hash": line["record_hash"], "seq": line["seq"], "content_json": json.dumps(content), "pilot": True,
        }]
    return found


class _Snapshot:
    """Everything the views read, loaded once from the store."""

    def __init__(self, store, protocol):
        self.store, self.protocol = store, protocol
        self.kinds = {r["model_version"]: r["kind"] for r in store.db.execute("SELECT * FROM model_versions")}
        self.version_of = {kind: version for version, kind in self.kinds.items()}
        self.matches = {r["match_uid"]: dict(r) for r in store.db.execute(
            "SELECT m.*, e.name AS edition_name, e.level, e.surface, e.tourney_date FROM matches m "
            "JOIN editions e ON e.edition_uid = m.edition_uid")}
        self.records = {}
        for r in store.db.execute(
                "SELECT o.match_uid, s.payload_json, s.retrieved_at FROM match_observations o "
                "JOIN source_records s ON s.record_id = o.record_id ORDER BY s.retrieved_at, s.record_id"):
            self.records[r["match_uid"]] = json.loads(r["payload_json"])        # the latest record wins
        self.predictions = defaultdict(list)
        for row in store.predictions():
            self.predictions[(row["match_uid"], row["model_version"])].append(row)
        self.decisions = defaultdict(list)
        for d in store.db.execute("SELECT * FROM eligibility_decisions ORDER BY decided_at, run_id"):
            self.decisions[(d["match_uid"], d["model_version"])].append(dict(d))
        self.settled = store.settled()
        self.counted = {(k[0], k[1]): v["prediction_id"] for k, v in counted(store, protocol).items()}
        self.seq_of = {row["prediction_id"]: row["seq"] for rows in self.predictions.values() for row in rows}
        self.pilots = load_pilots(self.matches, self.records, self.kinds)

    def rows(self, uid, version):
        """The match's stored forecasts for a model; for an approved pilot exception (and only when the store has
        none), its pilot forecast. Counting, the archive and the track record read self.predictions instead."""
        return self.predictions.get((uid, version)) or self.pilots.get((uid, version), [])

    # -- players and orientation
    def order(self, uid):
        """[player_a, player_b] of the match's first forecast (A is chosen from the match id, never the result), or
        None if no forecast exists."""
        rows = [r for version in self.kinds for r in self.rows(uid, version)]
        if not rows:
            return None
        first = min(rows, key=lambda r: r["seq"])
        return [first["player_a"], first["player_b"]]

    def players(self, uid):
        order = self.order(uid)
        rows = sorted((r for version in self.kinds for r in self.predictions.get((uid, version), [])),
                      key=lambda r: r["seq"])
        if not rows and order:                                 # a pilot exception: the observed players, in its order
            seen = self._observed(uid)
            if {p["id"] for p in seen} == set(order):
                return sorted(seen, key=lambda p: order.index(p["id"]))
        if rows:
            content = json.loads(rows[-1]["content_json"])["inputs"]["players"]
            by_id = {content[s]["player_id"]: content[s] for s in ("a", "b")}
            return [{"id": pid, "name": by_id[pid]["name"], "rank": by_id[pid].get("rank"),
                     "rank_as_of": _date(by_id[pid]["rank_as_of"]) if by_id[pid].get("rank_as_of") else None,
                     "seed": by_id[pid].get("seed"), "identity": by_id[pid].get("identity")} for pid in order]
        return self._observed(uid)

    def _observed(self, uid):
        """The two players as the latest source record names them, with canonical ids where identity is known."""
        record = self.records.get(uid) or {}
        match = self.matches[uid]
        found = []
        for side in ("home", "away"):
            seen = self.store.db.execute(
                "SELECT player_id, status FROM identity_observations WHERE provider = ? AND tour = ? AND "
                "provider_player_id = ? ORDER BY first_seen_at DESC LIMIT 1",
                (record.get("provider"), match["tour"], str(record.get(f"{side}_id")))).fetchone()
            pid = seen["player_id"] if seen and seen["player_id"] in (match["player_low"], match["player_high"]) else None
            found.append({"id": pid, "name": record.get(f"{side}_name"), "rank": record.get(f"{side}_rank"),
                          "rank_as_of": None, "seed": None, "identity": seen["status"] if pid else None})
        return found

    @staticmethod
    def aligned(row, order):
        """(probabilities in display order, sign that turns stored contributions into 'favours the first player')."""
        if row["player_a"] == order[0]:
            return [row["p_a"], 1 - row["p_a"]], 1.0
        return [1 - row["p_a"], row["p_a"]], -1.0

    # -- state
    def start(self, uid):
        record = self.records.get(uid) or {}
        return utc(record["event_time"]) if record.get("event_time") else None

    def state(self, uid, now):
        settlement = self.settled.get(uid)
        if settlement:
            return "result_conflict" if settlement["state"] == "conflict" else settlement["status"]
        record = self.records.get(uid) or {}
        raw = (record.get("raw_status") or "").upper()
        if "POSTPONED" in raw:
            return "postponed"
        if "SUSPENDED" in raw or "DELAYED" in raw:
            return "suspended"
        status = record.get("status")
        if status == "cancelled":
            return "cancelled"
        start = self.start(uid)
        # Once play may have begun, the site says only that the result is pending: the pre-match forecast stays as it
        # was, and nothing is shown about the match in progress (in-play estimates are a separate, later feature).
        if status in ("in_progress", "completed", "retired", "walkover") or (start and now >= start):
            return "result_pending"
        return "scheduled" if start else "time_tbc"

    def result(self, uid, order_ids):
        settlement = self.settled.get(uid)
        if not settlement:
            return None
        if settlement["state"] == "conflict":
            return {"status": "conflict", "winner_index": None, "score": None}
        winner = settlement["winner_id"]
        score = next((r["score"] for r in settlement["rows"] if r.get("score")), None)
        index = order_ids.index(winner) if winner in order_ids else None
        return {"status": settlement["status"], "winner_index": index, "score": score}

    # -- forecasts
    def forecast(self, uid, kind):
        version = self.version_of.get(kind)
        rows = self.rows(uid, version)
        if rows:
            order = self.order(uid)
            head_id = self.counted.get((uid, version))
            head = next((r for r in rows if r["prediction_id"] == head_id), rows[0])
            p, _ = self.aligned(head, order)
            latest = rows[-1]
            view = {"available": True, "model_version": version, "prediction_id": head["prediction_id"],
                    "issued_at": head["issued_at"], "p": p, "counted": head_id == head["prediction_id"],
                    "revision": None}
            if head.get("pilot"):
                view["pilot"] = True
            if latest["prediction_id"] != head["prediction_id"]:
                view["revision"] = {"prediction_id": latest["prediction_id"], "issued_at": latest["issued_at"],
                                    "p": self.aligned(latest, order)[0]}
            return view
        decisions = self.decisions.get((uid, version), [])
        last = decisions[-1] if decisions else None
        code, text = reasons.describe(last["decision"] if last else None, last["reason"] if last else None)
        return {"available": False, "model_version": version, "decision": last["decision"] if last else None,
                "reason_code": code, "reason": text}

    def summary(self, uid, now):
        match = self.matches[uid]
        players = self.players(uid)
        start = self.start(uid)
        record = self.records.get(uid) or {}
        return {
            "uid": uid, "tour": match["tour"], "round": match["round"], "best_of": record.get("best_of"),
            "edition": {"uid": match["edition_uid"], "name": match["edition_name"], "level": match["level"],
                        "surface": match["surface"], "start_date": _date(match["tourney_date"])},
            "start": iso(start) if start else None, "state": self.state(uid, now), "players": players,
            "forecasts": {kind: self.forecast(uid, kind) for kind in KINDS},
            "result": self.result(uid, [p["id"] for p in players]),
        }

    def missed(self, uid):
        """No forecast from either model because the match was first seen too close to its start, under way or already
        played (the owner's decision, 10 November 2026: such matches are not listed on the Match Center). Their match
        pages, decisions and the archive are unchanged."""
        for kind in KINDS:
            f = self.forecast(uid, kind)
            if f["available"] or not (f.get("decision") or "").startswith("too_late"):
                return False
        return True

    def listed(self, uid, now):
        """Whether a match belongs on the Match Center at `now`."""
        if self.missed(uid):
            return False
        match = self.matches[uid]
        start = self.start(uid)
        reference = start or _edition_start(match["tourney_date"])
        if uid in self.settled or self.state(uid, now) == "result_pending":
            return (now - reference).days < RESULT_DAYS
        return (now - _edition_start(match["tourney_date"])).days < EDITION_DAYS


# ---------------------------------------------------------------- views

def match_index(snap, now):
    entries = [snap.summary(uid, now) for uid in snap.matches if snap.listed(uid, now)]
    entries.sort(key=lambda m: (m["start"] is None, m["start"] or "", m["edition"]["name"], m["round"]))
    return {"schema_version": SCHEMA_VERSION, "generated_at": iso(now), "matches": _clean(entries)}


def _decision_log(snap, uid):
    """Each model's decisions, with consecutive repeats merged into one entry with a first and last time."""
    log = []
    for kind in KINDS:
        version = snap.version_of.get(kind)
        for d in snap.decisions.get((uid, version), []):
            if d["decision"] == "issued":
                code, text = "issued", "Forecast issued."
            elif d["decision"] == "unchanged":
                code, text = "unchanged", "Checked again: inputs unchanged, so no new forecast."
            else:
                code, text = reasons.describe(d["decision"], d["reason"])
            if log and log[-1]["model_version"] == version and log[-1]["code"] == code:
                log[-1]["last_at"], log[-1]["times"] = d["decided_at"], log[-1]["times"] + 1
            else:
                log.append({"model_version": version, "kind": kind, "decision": d["decision"], "code": code,
                            "text": text, "first_at": d["decided_at"], "last_at": d["decided_at"], "times": 1})
    return log


def _version_view(snap, row, order, kind):
    content = json.loads(row["content_json"])
    p, sign = snap.aligned(row, order)
    inputs = content["inputs"]
    side_of = {inputs["players"]["a"]["player_id"]: "a", inputs["players"]["b"]["player_id"]: "b"}
    fields = dict(PLAYER_INPUTS, **(ROUND_AWARE_INPUTS if kind == "round_aware" else {}))
    players = [{name: inputs["row"].get(f"{side_of[pid]}_{field}") for name, field in fields.items()} for pid in order]
    terms = sorted(((k, sign * v) for k, v in inputs["contributions"].items()), key=lambda kv: -abs(kv[1]))
    return {
        "prediction_id": row["prediction_id"], "issued_at": row["issued_at"], "scheduled_start": row["scheduled_start"],
        "p": p, "counted": snap.counted.get((row["match_uid"], row["model_version"])) == row["prediction_id"],
        "supersedes": row["supersedes"],
        "log_odds": sum(v for _, v in terms),
        "contributions": [{"feature": k, "log_odds": v} for k, v in terms],
        "inputs": players,
        "rank_source_dates": [_date(inputs["players"][side_of[pid]]["rank_as_of"])
                              if inputs["players"][side_of[pid]].get("rank_as_of") else None for pid in order],
        "integrity": {"input_sha256": row["input_sha256"], "model_sha256": content["model_sha256"],
                      "code_sha256": content.get("code_sha256"),
                      "code_matches_protocol": content.get("code_sha256") == snap.protocol["code_sha256"],
                      "record_hash": row["record_hash"], "ledger_position": row["seq"]},
        **({"pilot": True} if row.get("pilot") else {}),
    }


def match_page(snap, uid, now):
    summary = snap.summary(uid, now)
    order = snap.order(uid)
    versions = {}
    for kind in KINDS:
        version = snap.version_of.get(kind)
        versions[kind] = [_version_view(snap, row, order, kind) for row in snap.rows(uid, version)]
    outcomes = [{"source": o["source"], "status": o["status"], "score": o["score"],
                 "winner_index": order.index(o["winner_id"]) if order and o["winner_id"] in order else None,
                 "retrieved_at": o["retrieved_at"]} for o in snap.store.outcomes(uid)]
    return _clean({"schema_version": SCHEMA_VERSION, "generated_at": iso(now), "match": summary,
                   "versions": versions, "decisions": _decision_log(snap, uid), "outcomes": outcomes})


def _metrics(rows):
    m = prospective.metrics(rows)
    if m["n"] and m.get("log_loss_se") is not None and math.isfinite(m["log_loss_se"]):
        m["log_loss_low"], m["log_loss_high"] = m["log_loss"] - 1.96 * m["log_loss_se"], m["log_loss"] + 1.96 * m["log_loss_se"]
    return m


def track_record(snap, now):
    protocol, store = snap.protocol, snap.store
    window = protocol["window"]
    chosen = counted(store, protocol)
    rows, excluded = prospective.outcome_rows(store, chosen)
    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r["model_kind"]].append(r)
    issued = defaultdict(int)
    for row in store.predictions():
        if utc(row["issued_at"]) >= utc(window["issued_from"]):
            issued[snap.kinds[row["model_version"]]] += 1
    a, b = by_kind.get("tournament_start", []), by_kind.get("round_aware", [])
    later = {r["match_uid"] for r in b}
    return _clean({
        "schema_version": SCHEMA_VERSION, "generated_at": iso(now), "interim": True,
        "label": "Interim monitor of the prospective record P1. Not the P1 result; it decides nothing.",
        "protocol": {"name": protocol["name"], "frozen_at": protocol["frozen_at"], "issued_from": window["issued_from"],
                     "scheduled_up_to": window["scheduled_up_to"],
                     "final_evaluation_not_before": window["final_evaluation_not_before"],
                     "counted_forecast": protocol["counted_forecast"], "counted_matches": protocol["counted_matches"],
                     "reporting_rule": protocol["reporting_rule"], "code_sha256": protocol["code_sha256"]},
        "counts": {"issued": {k: issued.get(k, 0) for k in KINDS},
                   "counted": {k: sum(1 for key in chosen if snap.kinds[key[1]] == k) for k in KINDS},
                   "scored": {k: len(by_kind.get(k, [])) for k in KINDS},
                   "excluded": [{"reason": k, "n": v} for k, v in sorted(excluded.items())]},
        "tournament_start": {"all": _metrics(a), "ATP": _metrics([r for r in a if r["tour"] == "ATP"]),
                             "WTA": _metrics([r for r in a if r["tour"] == "WTA"]),
                             "surface_elo_benchmark": _metrics([dict(r, p=r["elo_probability"]) for r in a])},
        "round_aware": {"all": _metrics(b)},
        "round_aware_minus_tournament_start": prospective.paired(b, a),
        "tournament_start_on_same_matches": _metrics([r for r in a if r["match_uid"] in later]),
    })


def models_view(snap):
    found = []
    for model in api.models(snap.store):
        artifact = json.loads(snap.store.db.execute("SELECT artifact_json FROM model_versions WHERE model_version = ?",
                                                    (model["model_version"],)).fetchone()[0])
        model["features"] = {tour: spec["feature_names"] for tour, spec in artifact["tours"].items()}
        model["fit"] = artifact.get("fit")
        model["population"] = artifact.get("population")
        found.append(model)
    return _clean({"schema_version": SCHEMA_VERSION, "models": found})


def status_view(snap, now):
    store = snap.store
    last = {}
    failed_recent = 0
    for run in store.runs():
        if run["status"] == "ok":
            last[run["kind"]] = run["finished_at"]
        elif run["status"] == "failed" and (now - utc(run["started_at"])).days < 7:
            failed_recent += 1
    fresh = api.freshness(last, now)
    problems = api.verify_store(store)
    settled = snap.settled
    return _clean({
        "schema_version": SCHEMA_VERSION, "generated_at": iso(now),
        "ok": bool(fresh["ok"]) and not problems,
        "freshness": {k: fresh[k] for k in ("forecast", "settle", "espn_download")},
        "fresh": bool(fresh["ok"]), "stale_after_hours": api.STALE_AFTER_HOURS, "rule": fresh["rule"],
        "failed_runs_last_7_days": failed_recent,
        "counts": {"forecasts": len(store.predictions()), "matches": len(snap.matches),
                   "settled": sum(1 for s in settled.values() if s["state"] == "settled"),
                   "result_conflicts": sum(1 for s in settled.values() if s["state"] == "conflict")},
        "integrity": {"ok": not problems, "problems": len(problems),
                      "check": "every hash and every stored probability recomputed from its saved inputs"},
    })


def ledger_recent(snap):
    rows = snap.store.predictions()[-LEDGER_RECENT:]
    return _clean({"schema_version": SCHEMA_VERSION, "count": len(snap.store.predictions()),
                   "head": rows[-1]["record_hash"] if rows else None,
                   "entries": [{"position": r["seq"], "prediction_id": r["prediction_id"], "match_uid": r["match_uid"],
                                "model_version": r["model_version"], "issued_at": r["issued_at"],
                                "record_hash": r["record_hash"]} for r in reversed(rows)]})


# ---------------------------------------------------------------- archive and players (Phase 7 redesign)

def archive(snap, now):
    """Every forecast ever issued, newest first, with its match, whether it is the counted one, and the result.
    `favourite_won` is None until a completed result exists (retirements and walkovers are not scored)."""
    entries = []
    for (uid, version), rows in snap.predictions.items():
        order = snap.order(uid)
        summary = snap.summary(uid, now)
        result = summary["result"]
        settlement = snap.settled.get(uid)
        for row in rows:
            p, sign = snap.aligned(row, order)
            content = json.loads(row["content_json"])
            inputs = content["inputs"]
            fav = 0 if p[0] > p[1] else 1 if p[1] > p[0] else None
            won = None
            if result and result["status"] == "completed" and result["winner_index"] is not None and fav is not None:
                won = result["winner_index"] == fav
            entries.append({
                "prediction_id": row["prediction_id"], "match_uid": uid, "model_version": version,
                "kind": snap.kinds[version], "issued_at": row["issued_at"], "scheduled_start": row["scheduled_start"],
                "p": p, "players": [pl["name"] for pl in summary["players"]], "tour": summary["tour"],
                "event": summary["edition"]["name"], "round": summary["round"],
                "counted": snap.counted.get((uid, version)) == row["prediction_id"],
                "superseded": row["prediction_id"] != rows[-1]["prediction_id"],
                "result_status": result["status"] if result else None, "favourite_won": won,
                "record_hash": row["record_hash"], "ledger_position": row["seq"],
                # Inspection: everything below is copied from the stored forecast, oriented to the first player listed.
                "supersedes": row["supersedes"],
                "issued_before_start": bool(row["scheduled_start"]) and row["issued_at"] < row["scheduled_start"],
                "settled_at": settlement.get("settled_at") if settlement else None,
                "result_state": settlement.get("state") if settlement else None,
                "features": {k: sign * v for k, v in inputs["features"].items()},
                "contributions": sorted(([k, sign * v] for k, v in inputs["contributions"].items()), key=lambda kv: -abs(kv[1])),
                "integrity": {"input_sha256": row["input_sha256"], "model_sha256": content["model_sha256"],
                              "code_sha256": content.get("code_sha256"),
                              "code_matches_protocol": content.get("code_sha256") == snap.protocol["code_sha256"]},
            })
    entries.sort(key=lambda e: (e["issued_at"], e["ledger_position"]), reverse=True)
    return _clean({"schema_version": SCHEMA_VERSION, "generated_at": iso(now), "entries": entries})


PROFILE_INPUTS = ("elo", "surface_elo", "rank", "serve_points_won", "return_points_won", "form", "elo_matches",
                  "days_since_last_match")


def players_view(snap, now):
    """Player profiles built only from the model inputs stored with each forecast: what the model knew about a player
    at the time of their latest forecast, plus every forecast match on this site. No other player data is published."""
    found = {}
    for (uid, version), rows in snap.predictions.items():
        if snap.kinds[version] != "tournament_start":
            continue
        order = snap.order(uid)
        summary = snap.summary(uid, now)
        head = next((r for r in rows if snap.counted.get((uid, version)) == r["prediction_id"]), rows[0])
        view = _version_view(snap, head, order, "tournament_start")
        for i, pid in enumerate(order):
            player = summary["players"][i]
            entry = found.setdefault(pid, {"id": pid, "name": player["name"], "tour": summary["tour"], "matches": [],
                                           "latest": None})
            opponent = summary["players"][1 - i]["name"]
            result = summary["result"]
            outcome = None
            if result and result["status"] == "completed" and result["winner_index"] is not None:
                outcome = "won" if result["winner_index"] == i else "lost"
            entry["matches"].append({
                "match_uid": uid, "start": summary["start"], "event": summary["edition"]["name"],
                "surface": summary["edition"]["surface"], "round": summary["round"], "opponent": opponent,
                "p": view["p"][i], "issued_at": view["issued_at"], "outcome": outcome,
            })
            snapshot = {k: view["inputs"][i].get(k) for k in PROFILE_INPUTS}
            if entry["latest"] is None or view["issued_at"] > entry["latest"]["issued_at"]:
                entry["latest"] = {"issued_at": view["issued_at"], "surface": summary["edition"]["surface"],
                                   "rank_as_of": view["rank_source_dates"][i], "identity": player["identity"],
                                   "inputs": snapshot}
    players = sorted(found.values(), key=lambda p: (p["latest"]["inputs"]["rank"] is None, p["latest"]["inputs"]["rank"] or 0, p["name"] or ""))
    for p in players:
        p["matches"].sort(key=lambda m: m["start"] or "", reverse=True)
    return _clean({"schema_version": SCHEMA_VERSION, "generated_at": iso(now), "players": players})

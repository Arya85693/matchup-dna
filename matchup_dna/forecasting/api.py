"""The read-only interface between the forecasting engine and the future website.

Every function takes a Store and returns plain JSON-ready dicts. A web framework (FastAPI, per the brief) would wrap
these functions one-to-one, with no forecasting logic in the route handlers; the website never calls a data provider.

    upcoming(store, now)       pending matches with both models' forecasts, or each model's reason for having none
    match_detail(store, uid)   every forecast ever issued for a match (superseded ones included), decisions, results
    track_record(store)        settled forecasts with their results, for the history and calibration pages
    models(store)              each model version: what information it uses, and its artifact hash
    status(store)              freshness of the last runs, counts, integrity, identity changes

Rules the payloads encode:
- A model's forecast appears only if that model issued one. If Model B (round-aware) did not, the payload says why and
  carries no number. Model A's number is never shown in Model B's place.
- Probabilities are given per player id, so a page never has to know which player was "A".
- Every forecast carries its model version, issue time and prediction id; a page shows when it was issued.
- Model B is described as using the same pre-tournament information as Model A plus completed earlier rounds of the
  same tournament. It is not an independent model, and it is not a live point-by-point model.
"""
import json
from collections import defaultdict

from matchup_dna.forecasting.records import iso, utc

MODEL_INFO = {
    "tournament_start": {
        "label": "Tournament-start forecast",
        "uses": ["overall and surface Elo ratings before the tournament", "ATP/WTA ranking (and whether a player is "
                 "unranked)", "days since each player's last match", "recent form against Elo expectations",
                 "opponent-adjusted serve and return estimates from earlier matches"],
        "does_not_use": ["results from the same tournament", "injury or withdrawal news", "betting prices",
                         "anything after the tournament started"],
    },
    "round_aware": {
        "label": "Round-aware update",
        "uses": ["everything the tournament-start forecast uses", "results of this tournament's completed earlier "
                 "rounds: an Elo update round by round, and each player's share of games won so far"],
        "does_not_use": ["live scores or points", "injury or withdrawal news", "betting prices",
                         "the result of the match itself or any later round"],
        "applies_to": "knockout matches after the first round in which at least one player has already played",
    },
}


def _content(row):
    return json.loads(row["content_json"])


def _forecast_view(row, superseded):
    content = _content(row)
    players = content["inputs"]["players"]
    contributions = sorted(content["inputs"]["contributions"].items(), key=lambda kv: -abs(kv[1]))
    return {
        "available": True, "prediction_id": row["prediction_id"], "model_version": row["model_version"],
        "issued_at": row["issued_at"],
        "probabilities": {str(players["a"]["player_id"]): row["p_a"], str(players["b"]["player_id"]): 1 - row["p_a"]},
        "explanation": {"favours": "positive values favour " + players["a"]["name"],
                        "terms": [{"feature": k, "log_odds": v} for k, v in contributions]},
        "earlier_versions": superseded,
    }


def _forecasts_for(store, uid):
    """{kind: view} with each model's latest forecast, or its latest decision's reason."""
    found = {}
    versions = store.db.execute("SELECT model_version, kind FROM model_versions").fetchall()
    for version in versions:
        rows = store.db.execute("SELECT * FROM predictions WHERE match_uid = ? AND model_version = ? ORDER BY seq",
                                (uid, version["model_version"])).fetchall()
        if rows:
            found[version["kind"]] = _forecast_view(rows[-1], len(rows) - 1)
        else:
            decision = store.db.execute(
                "SELECT d.* FROM eligibility_decisions d JOIN runs r ON r.run_id = d.run_id WHERE d.match_uid = ? AND "
                "d.model_version = ? ORDER BY d.decided_at DESC LIMIT 1", (uid, version["model_version"])).fetchone()
            found[version["kind"]] = {"available": False, "model_version": version["model_version"],
                                      "reason": decision["reason"] if decision else "not evaluated yet",
                                      "decision": decision["decision"] if decision else None}
    return found


def _fixture_of(store, uid):
    """The latest provider record describing the match."""
    row = store.db.execute(
        "SELECT s.payload_json, s.retrieved_at FROM match_observations o JOIN source_records s ON s.record_id = o.record_id "
        "WHERE o.match_uid = ? ORDER BY s.retrieved_at DESC, s.record_id DESC LIMIT 1", (uid,)).fetchone()
    return (json.loads(row["payload_json"]), row["retrieved_at"]) if row else (None, None)


def upcoming(store, now, include_started_hours=3):
    """Matches not yet settled whose latest scheduled start is after now minus `include_started_hours`."""
    settled = store.settled()
    found = []
    for match in store.db.execute("SELECT m.*, e.name AS tournament, e.surface, e.level, e.tourney_date FROM matches m "
                                  "JOIN editions e ON e.edition_uid = m.edition_uid"):
        if match["match_uid"] in settled:
            continue
        record, retrieved = _fixture_of(store, match["match_uid"])
        start = utc(record["event_time"]) if record and record.get("event_time") else None
        if start is None or (utc(now) - start).total_seconds() > include_started_hours * 3600:
            continue
        found.append({
            "match_uid": match["match_uid"], "tour": match["tour"], "tournament": match["tournament"],
            "round": match["round"], "surface": match["surface"], "scheduled_start": iso(start),
            "best_of": record.get("best_of") if record else None,
            "players": _players(store, match["match_uid"], record),
            "forecasts": _forecasts_for(store, match["match_uid"]),
            "data": {"fixture_retrieved_at": retrieved, "provider": record["provider"] if record else None},
        })
    found.sort(key=lambda m: m["scheduled_start"])
    return {"generated_at": iso(now), "matches": found, "models": MODEL_INFO}


def _players(store, uid, record):
    rows = store.db.execute("SELECT content_json FROM predictions WHERE match_uid = ? ORDER BY seq DESC LIMIT 1",
                            (uid,)).fetchall()
    if rows:
        players = json.loads(rows[0]["content_json"])["inputs"]["players"]
        return [{k: players[s][k] for k in ("player_id", "name", "rank", "identity")} for s in ("a", "b")]
    if record:
        match = store.match(uid)
        return [{"player_id": None, "name": record["home_name"], "rank": record["home_rank"], "identity": None,
                 "candidates": [match["player_low"], match["player_high"]]},
                {"player_id": None, "name": record["away_name"], "rank": record["away_rank"], "identity": None,
                 "candidates": [match["player_low"], match["player_high"]]}]
    return []


def match_detail(store, uid):
    predictions = [dict(r, content=_content(r)) for r in store.db.execute(
        "SELECT * FROM predictions WHERE match_uid = ? ORDER BY seq", (uid,))]
    return {
        "match": store.match(uid),
        "predictions": [{k: p[k] for k in ("prediction_id", "model_version", "issued_at", "scheduled_start",
                                           "player_a", "player_b", "p_a", "supersedes", "record_hash")}
                        for p in predictions],
        "decisions": [dict(r) for r in store.db.execute(
            "SELECT * FROM eligibility_decisions WHERE match_uid = ? ORDER BY decided_at", (uid,))],
        "outcomes": store.outcomes(uid),
        "settlement": {k: v for k, v in store.settled().get(uid, {}).items() if k != "rows"},
    }


def track_record(store):
    settled = store.settled()
    found = []
    for row in store.predictions():
        settlement = settled.get(row["match_uid"])
        if not settlement or settlement["state"] != "settled":
            continue
        found.append({"prediction_id": row["prediction_id"], "match_uid": row["match_uid"],
                      "model_version": row["model_version"], "issued_at": row["issued_at"],
                      "p_a": row["p_a"], "player_a": row["player_a"], "status": settlement["status"],
                      "a_won": None if settlement["winner_id"] is None else int(settlement["winner_id"] == row["player_a"])})
    return found


def models(store):
    return [{"model_version": r["model_version"], "kind": r["kind"], "artifact_sha256": r["artifact_sha256"],
             "registered_at": r["registered_at"], **MODEL_INFO.get(r["kind"], {})}
            for r in store.db.execute("SELECT * FROM model_versions")]


def status(store):
    runs = store.runs()
    last = defaultdict(lambda: None)
    for run in runs:
        if run["status"] == "ok":
            last[run["kind"]] = run["finished_at"]
    decisions = defaultdict(int)
    for d in store.decisions():
        decisions[f"{d['model_version']}: {d['decision']}"] += 1
    settled = store.settled()
    return {
        "mode": store.mode, "last_successful": dict(last),
        "failed_runs": [r["run_id"] for r in runs if r["status"] != "ok"],
        "predictions": len(store.predictions()), "matches": store.db.execute("SELECT COUNT(*) FROM matches").fetchone()[0],
        "decisions": dict(decisions),
        "settled": sum(1 for s in settled.values() if s["state"] == "settled"),
        "conflicting_results": [uid for uid, s in settled.items() if s["state"] == "conflict"],
        "integrity_problems": store.verify(), "identity_changes": store.identity_drift(),
    }


def verify_store(store):
    """Hash chain and content hashes, then every probability recomputed from its stored input row with the stored
    model artifact. Returns a list of problems (empty if every forecast reproduces exactly)."""
    from matchup_dna.forecasting.engine import reproduce
    from matchup_dna.forecasting.frozen_models import FrozenModel
    problems = store.verify()
    artifacts = {r["model_version"]: FrozenModel(r["artifact_json"])
                 for r in store.db.execute("SELECT * FROM model_versions")}
    for row in store.predictions():
        content = _content(row)
        model = artifacts[row["model_version"]]
        if model.sha256 != content["model_sha256"]:
            problems.append(f"{row['prediction_id']}: stored artifact hash differs")
            continue
        p = reproduce(content, model)
        if p != row["p_a"]:
            problems.append(f"{row['prediction_id']}: recomputed {p!r}, stored {row['p_a']!r}")
    return problems

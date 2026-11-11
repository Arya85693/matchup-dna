"""The website's ITF file (itf.json), built from a read-only copy of the ITF store (data/store/itf.sqlite).

    upcoming   every ITF match with a stored M1 forecast and no result yet: players, event, tier, round, start time,
               M1's probability for player A, and the Elo-only probability beside it
    recent     the latest settled matches with their counted forecast and result
    record     P2's counting rule: each match's first M1 forecast counts, if issued after P2 was frozen (forecasts
               before the freeze are a pilot: shown, never scored); completed matches are scored (retirements and
               walkovers are not); log loss, Brier and accuracy for M1 and Elo-only on the same matches
    research   the frozen held-out and validation results (web/content/research/itf.json, from the Model Report)
    archive    every M1 forecast (revisions too), newest first, with its prediction id, chain hash, counting status
               (counted / pilot / revision) and the Elo-only forecast for the same match
    board      the ITF players board the last ITF run wrote (data/raw/itf/board.json): active ITF players by the
               ITF rating, with ATP or WTA rank and 52-week ITF record; display only, never a forecast input

Nothing here computes a forecast: every probability is read from the store.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "web" / "content" / "research" / "itf.json"
ITF_PROTOCOL = ROOT / "experiments" / "itf_prospective_protocol.json"
BOARD = ROOT / "data" / "raw" / "itf" / "board.json"
MODEL, BASELINE = "itf-m1-v1", "itf-elo-v1"
RECENT = 60
# The Sackmann part of the ITF model's history: every level from 2010 to the snapshot of 1 June 2026, ATP 461,658 and
# WTA 405,738 matches. The snapshot never changes; the daily ITF players export recounts it and warns on a difference.
ITF_SACKMANN_MATCHES = 867_396
UPCOMING = 300
ARCHIVE = 1500


def _first(predictions):
    """{match_uid: first prediction} in chain order (P2's counting rule)."""
    found = {}
    for p in predictions:
        found.setdefault(p["match_uid"], p)
    return found


def _reliability(rows, bins=10):
    """Ten equal-width bins of the forecast for the first-named player: matches, mean forecast, share won."""
    found = []
    for b in range(bins):
        inside = [(p, won) for p, won in rows if min(int(p * bins), bins - 1) == b]
        if inside:
            found.append({"bin": f"{b / bins:.1f}-{(b + 1) / bins:.1f}", "matches": len(inside),
                          "forecast": sum(p for p, _ in inside) / len(inside),
                          "observed": sum(w for _, w in inside) / len(inside)})
    return found


def _score(rows):
    if not rows:
        return {"matches": 0, "log_loss": None, "brier": None, "accuracy": None, "reliability": []}
    loss = brier = right = 0.0
    for p, won in rows:
        p = min(max(p, 1e-12), 1 - 1e-12)
        loss -= math.log(p) if won else math.log(1 - p)
        brier += (p - won) ** 2
        right += (p > 0.5) == bool(won)
    n = len(rows)
    return {"matches": n, "log_loss": loss / n, "brier": brier / n, "accuracy": right / n,
            "reliability": _reliability(rows)}


def build(store, now_iso, protocol_path=ITF_PROTOCOL, research_path=RESEARCH, board_path=BOARD):
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8")) if Path(protocol_path).exists() else None
    model = _first(store.predictions(MODEL))
    baseline = _first(store.predictions(BASELINE))
    counted_from = protocol["frozen_at"] if protocol else None
    settled = store.settled()
    upcoming, recent, scored_model, scored_base = [], [], [], []
    for uid, p in model.items():
        content = json.loads(p["content_json"])
        base = baseline.get(uid)
        entry = {"uid": uid, "tour": content["inputs"]["tour"], "event": content.get("event"),
                 "tier": content["inputs"]["tier"], "surface": content["inputs"]["surface"],
                 "round": content["inputs"]["round"], "start": p["scheduled_start"], "issued_at": p["issued_at"],
                 "a": content.get("a_name"), "b": content.get("b_name"), "p_a": p["p_a"],
                 "p_a_elo": base["p_a"] if base else None}
        s = settled.get(uid)
        if s is None:
            upcoming.append(entry)
            continue
        if s["state"] != "settled":
            continue
        won = None if s["winner_id"] is None else int(s["winner_id"] == p["player_a"])
        recent.append(dict(entry, status=s["status"], winner=None if won is None else ("a" if won else "b"),
                           score=next((r["score"] for r in s["rows"] if r["score"]), "")))
        counted = counted_from is not None and p["issued_at"] >= counted_from
        if counted and s["status"] == "completed" and won is not None:
            scored_model.append((p["p_a"], won))
            if base:
                scored_base.append((base["p_a"], won))
    archive = []
    for p in sorted(store.predictions(MODEL), key=lambda r: -r["seq"])[:ARCHIVE]:
        content = json.loads(p["content_json"])
        first = model.get(p["match_uid"])
        is_first = first is not None and first["prediction_id"] == p["prediction_id"]
        status = "revision" if not is_first else (
            "counted" if counted_from is not None and p["issued_at"] >= counted_from else "pilot")
        s = settled.get(p["match_uid"])
        base = baseline.get(p["match_uid"])
        archive.append({"seq": p["seq"], "prediction_id": p["prediction_id"], "record_hash": p["record_hash"],
                        "uid": p["match_uid"], "issued_at": p["issued_at"], "start": p["scheduled_start"],
                        "tour": content["inputs"]["tour"], "event": content.get("event"), "round": content["inputs"]["round"],
                        "a": content.get("a_name"), "b": content.get("b_name"), "p_a": p["p_a"],
                        "p_a_elo": base["p_a"] if base else None, "status": status,
                        "result": None if not s or s["state"] != "settled" else s["status"],
                        "winner": None if not s or s["state"] != "settled" or s["winner_id"] is None
                        else ("a" if s["winner_id"] == p["player_a"] else "b")})
    upcoming.sort(key=lambda e: e["start"] or "")
    recent.sort(key=lambda e: e["start"] or "", reverse=True)
    return {
        "generated_at": now_iso,
        "model": {"version": MODEL, "baseline": BASELINE,
                  "description": "M1: all-level Elo, surface Elo, rank, rest, form and tier. No serve statistics: "
                                 "none are published for ITF matches."},
        "protocol": {"frozen": protocol is not None, "frozen_at": protocol["frozen_at"] if protocol else None},
        "upcoming": upcoming[:UPCOMING],
        "archive": archive,
        "recent": recent[:RECENT],
        "record": {"forecast_matches": len(model), "settled": sum(1 for u in model if u in settled),
                   "m1": _score(scored_model), "elo": _score(scored_base)},
        "research": json.loads(Path(research_path).read_text(encoding="utf-8")),
        "board": json.loads(Path(board_path).read_text(encoding="utf-8")) if Path(board_path).exists() else None,
        "history": history(store),
    }


def history(store):
    """The size of the history the latest finished ITF run read: the Sackmann snapshot plus the Flashscore results it
    added (both players resolved, not already in Sackmann). None before the first finished run."""
    for run in reversed(list(store.runs("itf_forecast"))):
        counts = json.loads(run["counts_json"] or "{}")
        if run["status"] == "ok" and "ATP history added" in counts:
            added = counts["ATP history added"] + counts.get("WTA history added", 0)
            return {"matches": ITF_SACKMANN_MATCHES + added, "flashscore_added": added, "as_of": run["as_of"] or run["started_at"]}
    return {"matches": None, "flashscore_added": None, "as_of": None}

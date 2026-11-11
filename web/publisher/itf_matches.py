"""ITF matches in the main-tour formats, so the site's match board, match pages and archive show them the same way.

    itf/matches.json        the match board (the main-tour matches/index.json format)
    itf/match-pages.json    every ITF match page (the main-tour matches/<uid>.json format), in one file keyed by
                            match uid: every publish uploads every file, so one file per ITF match would multiply the
                            uploads by hundreds
    itf/archive.json        every ITF M1 forecast (the main-tour archive.json format)

Model mapping: the ITF model M1 is a tournament-start model, so it fills the "tournament_start" slot. ITF has no
round-aware model; that slot always carries a plain reason, as the main tour's does for first-round matches.

Contributions are not stored with ITF forecasts (P2's code is frozen), so they are rebuilt here from each forecast's
stored inputs and the frozen model file (models/itf_m1.json): the design columns times the stored weights. The
rebuilt log-odds must give back the stored probability to within 1e-9, or the publish stops. Nothing new is forecast.
"""
import datetime
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "itf_m1.json"
MODEL, BASELINE = "itf-m1-v1", "itf-elo-v1"
ROUND_AWARE_REASON = "The ITF model has no round-aware version: this forecast uses information from before the event."
SCHEMA_VERSION = "1"
FINISHED = ("completed", "retired", "walkover")


class ContributionError(ValueError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _day(yyyymmdd):
    s = str(yyyymmdd)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _logit(p):
    return math.log(p) - math.log1p(-p)


class Explainer:
    """Rebuilds each stored M1 forecast's contributions from its inputs and the frozen model."""

    def __init__(self, path=MODEL_PATH):
        from matchup_dna.itf_live import FrozenITF
        text = Path(path).read_text(encoding="utf-8")
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.models = {tour: FrozenITF(spec) for tour, spec in json.loads(text)["tours"].items()}

    @staticmethod
    def row(inputs):
        row = dict(inputs)
        row.update(a_serve_attempts=0, b_serve_attempts=0)
        for side in ("a", "b"):
            for field in ("serve", "return", "serve_adjusted", "return_adjusted"):
                row[f"{side}_{field}"] = 0.5
        return row

    def contributions(self, inputs, p_a):
        """[(feature, log-odds toward player A)], checked against the stored probability."""
        from matchup_dna import itf_model
        model = self.models[inputs["tour"]]
        x = itf_model.design([self.row(inputs)], model.names, model.prep)[0] / model.scale
        terms = [(name, float(v)) for name, v in zip(model.names, x * model.coefficients)]
        if abs(sum(v for _, v in terms) - _logit(p_a)) > 1e-9:
            raise ContributionError(f"rebuilt contributions do not give back the stored probability {p_a}")
        return sorted(terms, key=lambda t: -abs(t[1]))


def _player_inputs(inputs, side):
    return {"elo": inputs[f"{side}_elo"], "surface_elo": None, "elo_matches": inputs[f"{side}_elo_matches"],
            "surface_matches": inputs.get(f"{side}_surface_matches"), "rank": inputs[f"{side}_rank"],
            "days_since_last_match": inputs[f"{side}_days_since"], "form": inputs[f"{side}_form"],
            "serve_points_won": None, "return_points_won": None}


class _ItfSnapshot:
    def __init__(self, store, protocol):
        self.store, self.protocol = store, protocol
        self.frozen_at = protocol["frozen_at"] if protocol else None
        self.protocol_code = protocol["code_sha256"] if protocol else None
        db = store.db
        self.matches = {r["match_uid"]: dict(r) for r in db.execute("SELECT * FROM matches")}
        self.editions = {r["edition_uid"]: dict(r) for r in db.execute("SELECT * FROM editions")}
        self.runs = {r["run_id"]: json.loads(r["inputs_json"]) for r in db.execute("SELECT run_id, inputs_json FROM runs")}
        self.rows = defaultdict(list)
        for p in store.predictions(MODEL):
            self.rows[p["match_uid"]].append(p)
        self.baseline = {}
        for p in store.predictions(BASELINE):
            self.baseline.setdefault(p["match_uid"], p)
        self.settled = store.settled()
        self.explainer = Explainer()
        from matchup_dna.load import load_players
        try:
            self.full_names = {key: p["name"] for key, p in load_players().items() if p.get("name")}
        except FileNotFoundError:           # without Sackmann's player files, Flashscore's short names are shown
            self.full_names = {}

    def name(self, tour, player_id, fallback):
        return self.full_names.get((tour, player_id)) or fallback

    def counted(self, row):
        first = self.rows[row["match_uid"]][0]
        return row["prediction_id"] == first["prediction_id"] and self.frozen_at is not None \
            and row["issued_at"] >= self.frozen_at

    def code(self, row):
        hashes = self.runs.get(row["run_id"], {}).get("code_sha256")
        return (_sha(hashes) if hashes else None), (hashes == self.protocol_code if hashes and self.protocol_code else False)

    def state(self, uid, start, now):
        s = self.settled.get(uid)
        if s and s["state"] == "settled":
            return s["status"]
        if s and s["state"] == "conflict":
            return "result_conflict"
        if start and start <= now:
            return "result_pending"
        return "scheduled" if start else "time_tbc"

    def summary(self, uid, now_iso):
        rows = self.rows[uid]
        first, latest = rows[0], rows[-1]
        content = json.loads(first["content_json"])
        inputs = content["inputs"]
        match, edition = self.matches[uid], self.editions[self.matches[uid]["edition_uid"]]
        order = (first["player_a"], first["player_b"])
        identity = content.get("identity") or [None, None]
        players = []
        for i, side in enumerate(("a", "b")):
            players.append({"id": order[i], "name": self.name(match["tour"], order[i], content.get(f"{side}_name")),
                            "rank": inputs.get(f"{side}_rank"),
                            "rank_as_of": None, "seed": None, "identity": identity[i] if i < len(identity) else None})
        start = latest["scheduled_start"]
        forecast = {"available": True, "model_version": MODEL, "prediction_id": first["prediction_id"],
                    "issued_at": first["issued_at"], "p": [first["p_a"], 1 - first["p_a"]],
                    "counted": self.counted(first),
                    "revision": None if latest is first else {"prediction_id": latest["prediction_id"],
                                                               "issued_at": latest["issued_at"],
                                                               "p": [latest["p_a"], 1 - latest["p_a"]]}}
        s = self.settled.get(uid)
        result = None
        if s and s["state"] == "settled":
            score = next((r["score"] for r in s["rows"] if r["score"]), None)
            result = {"status": s["status"], "score": score,
                      "winner_index": order.index(s["winner_id"]) if s["winner_id"] in order else None}
        return {"uid": uid, "tour": match["tour"], "round": match["round"], "best_of": 3,
                "edition": {"uid": edition["edition_uid"], "name": edition["name"], "level": edition["level"],
                            "surface": edition["surface"], "start_date": _day(edition["tourney_date"])},
                "start": start, "state": self.state(uid, start, now_iso), "players": players,
                "forecasts": {"tournament_start": forecast,
                              "round_aware": {"available": False, "model_version": MODEL, "decision": None,
                                              "reason_code": "itf_no_round_aware", "reason": ROUND_AWARE_REASON}},
                "result": result}

    def version(self, row):
        content = json.loads(row["content_json"])
        inputs = content["inputs"]
        terms = self.explainer.contributions(inputs, row["p_a"])
        code_sha, matches = self.code(row)
        return {"prediction_id": row["prediction_id"], "issued_at": row["issued_at"],
                "scheduled_start": row["scheduled_start"], "p": [row["p_a"], 1 - row["p_a"]],
                "counted": self.counted(row), "supersedes": row["supersedes"],
                "log_odds": sum(v for _, v in terms),
                "contributions": [{"feature": k, "log_odds": v} for k, v in terms],
                "inputs": [_player_inputs(inputs, "a"), _player_inputs(inputs, "b")],
                "rank_source_dates": [None, None],
                "integrity": {"input_sha256": row["input_sha256"], "model_sha256": content["model_sha256"],
                              "code_sha256": code_sha, "code_matches_protocol": matches,
                              "record_hash": row["record_hash"], "ledger_position": row["seq"]}}

    def decisions(self, uid):
        grouped = {}
        for d in self.store.decisions():
            if d["match_uid"] != uid or d["model_version"] != MODEL:
                continue
            key = d["decision"]
            entry = grouped.setdefault(key, {"model_version": MODEL, "kind": "tournament_start", "decision": key,
                                             "code": key, "text": {"issued": "Forecast issued", "unchanged":
                                                                   "Re-checked: inputs unchanged"}.get(key, key),
                                             "first_at": d["decided_at"], "last_at": d["decided_at"], "times": 0})
            entry["first_at"] = min(entry["first_at"], d["decided_at"])
            entry["last_at"] = max(entry["last_at"], d["decided_at"])
            entry["times"] += 1
        return sorted(grouped.values(), key=lambda e: e["first_at"])

    def page(self, uid, now_iso):
        summary = self.summary(uid, now_iso)
        order = tuple(p["id"] for p in summary["players"])
        outcomes = [{"source": o["source"], "status": o["status"], "score": o["score"],
                     "winner_index": order.index(o["winner_id"]) if o["winner_id"] in order else None,
                     "retrieved_at": o["retrieved_at"]} for o in self.store.outcomes(uid)]
        return {"schema_version": SCHEMA_VERSION, "generated_at": now_iso, "match": summary,
                "versions": {"tournament_start": [self.version(r) for r in self.rows[uid]], "round_aware": []},
                "decisions": self.decisions(uid), "outcomes": outcomes}

    def archive_entries(self):
        entries = []
        for uid, rows in self.rows.items():
            s = self.settled.get(uid)
            for i, row in enumerate(rows):
                content = json.loads(row["content_json"])
                inputs = content["inputs"]
                terms = self.explainer.contributions(inputs, row["p_a"])
                code_sha, matches = self.code(row)
                won = None
                if s and s["state"] == "settled" and s["status"] == "completed" and s["winner_id"] is not None:
                    favourite = row["player_a"] if row["p_a"] >= 0.5 else row["player_b"]
                    won = s["winner_id"] == favourite
                entries.append({
                    "prediction_id": row["prediction_id"], "match_uid": uid, "model_version": MODEL,
                    "kind": "tournament_start", "issued_at": row["issued_at"], "scheduled_start": row["scheduled_start"],
                    "p": [row["p_a"], 1 - row["p_a"]],
                    "players": [self.name(inputs["tour"], row["player_a"], content.get("a_name")),
                                self.name(inputs["tour"], row["player_b"], content.get("b_name"))],
                    "tour": inputs["tour"], "event": content.get("event") or "", "round": inputs["round"],
                    "counted": self.counted(row), "superseded": i < len(rows) - 1,
                    "result_status": s["status"] if s and s["state"] == "settled" else None,
                    "favourite_won": won, "record_hash": row["record_hash"], "ledger_position": row["seq"],
                    "supersedes": row["supersedes"],
                    "issued_before_start": bool(row["scheduled_start"]) and row["issued_at"] < row["scheduled_start"],
                    "settled_at": s.get("settled_at") if s and s["state"] == "settled" else None,
                    "result_state": s["state"] if s else None,
                    "features": {k: v for k, v in {"elo_diff": inputs["elo_diff"],
                                                   "surface_elo_diff": inputs["surface_elo_diff"]}.items()
                                 if v is not None},
                    "contributions": [[k, v] for k, v in terms],
                    "integrity": {"input_sha256": row["input_sha256"], "model_sha256": content["model_sha256"],
                                  "code_sha256": code_sha, "code_matches_protocol": matches}})
        entries.sort(key=lambda e: e["ledger_position"], reverse=True)
        return entries


def build(store, now_iso, protocol):
    """{published path: document} for the three ITF match files."""
    snap = _ItfSnapshot(store, protocol)
    summaries = [snap.summary(uid, now_iso) for uid in snap.rows]
    summaries.sort(key=lambda m: (m["start"] or "", m["uid"]))
    return {
        "itf/matches.json": {"schema_version": SCHEMA_VERSION, "generated_at": now_iso, "matches": summaries},
        "itf/match-pages.json": {"schema_version": SCHEMA_VERSION, "generated_at": now_iso,
                                 "pages": {uid: snap.page(uid, now_iso) for uid in snap.rows}},
        "itf/archive.json": {"schema_version": SCHEMA_VERSION, "generated_at": now_iso,
                             "entries": snap.archive_entries()},
    }

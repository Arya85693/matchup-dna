"""The website's ITF file: P2's counting rule, the scores, and that it is built from a read-only copy."""
import datetime
import json
import math
import tempfile
import unittest
from pathlib import Path

from matchup_dna import itf_live as live
from matchup_dna.forecasting.store import Store
from web.publisher import contract, itf_view, publish

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 11, 8, 0, tzinfo=UTC)


def place(mid, a, b, start="2026-11-11T12:00:00Z"):
    return {"tour": "ATP", "tourney_id": "fs:itf-men-singles:m15-test:20261109", "tourney_date": 20261109,
            "event": "M15 Test", "tourney_level": "15", "surface": "Clay", "round": "R32", "provider_match_id": mid,
            "start": start, "identity": ("verified", "verified"), "winner_id": a, "loser_id": b, "winner_name": "A",
            "loser_name": "B", "home_provider_id": f"h{mid}", "away_provider_id": f"a{mid}"}


def row(a, b, a_elo=1500.0, b_elo=1500.0):
    r = {f: 0 for f in live.INPUT_FIELDS}
    r.update(a_id=a, b_id=b, a_elo=a_elo, b_elo=b_elo, a_name=f"P{a}", b_name=f"P{b}", tour="ATP", surface="Clay",
             round="R32", tier=1, tourney_date=20261109)
    return r


class ItfViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "itf.sqlite"
        store = Store(self.path, "live")
        with store.transaction():
            store.start_run("r1", "itf_forecast", "2026-11-11T08:00:00Z", {})
            store.register_model(live.MODEL_VERSION, "itf_tournament_start", "{}", "m" * 64)
            store.register_model(live.BASELINE_VERSION, "itf_elo_only", "{}", "b" * 64)
            live.issue(store, "r1", NOW, place("x1", 1, 2), row(1, 2, 1600, 1500), 0.7, "m" * 64, "b" * 64)
            live.issue(store, "r1", NOW, place("x2", 3, 4), row(3, 4), 0.4, "m" * 64, "b" * 64)
            live.issue(store, "r1", NOW, place("x3", 5, 6), row(5, 6), 0.55, "m" * 64, "b" * 64)
            store.start_run("r2", "itf_forecast", "2026-11-11T09:00:00Z", {})
            live.issue(store, "r2", NOW, place("x1", 1, 2), row(1, 2, 1700, 1500), 0.9, "m" * 64, "b" * 64)  # revision
            uid1, uid2 = (store.match_for_alias("flashscore", "ATP", m) for m in ("x1", "x2"))
            store.add_outcome(uid1, "flashscore", "x1", "completed", 1, "6-3 6-4", 3, NOW, NOW, "r2")
            store.add_outcome(uid2, "flashscore", "x2", "retired", 4, "6-3 2-0", 3, NOW, NOW, "r2")
            store.finish_run("r1", "ok", {})
            store.finish_run("r2", "ok", {})
        store.close()

        self.board = Path(self.tmp.name) / "board.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_board_is_included_when_an_itf_run_has_written_one(self):
        self.assertIsNone(self.build()["board"])
        self.board.write_text(json.dumps({"generated_at": "2026-11-11T08:00:00Z", "rank_lists": {"ATP": "2026-11-09"},
                                          "min_matches": 5, "tours": {"ATP": [{"id": 1, "name": "A", "country": "ESP",
                                          "rating": 1650.0, "rank": 412, "wins": 9, "losses": 4, "last_event": 20261109,
                                          "position": 1}], "WTA": []}}), encoding="utf-8")
        self.assertEqual(self.build()["board"]["tours"]["ATP"][0]["rank"], 412)

    def build(self, protocol=None):
        from web.publisher.readonly import open_readonly
        path = Path(self.tmp.name) / "protocol.json"
        if protocol:
            path.write_text(json.dumps(protocol), encoding="utf-8")
        store = open_readonly(self.path)
        try:
            return itf_view.build(store, "2026-11-11T10:00:00Z", protocol_path=path, board_path=self.board)
        finally:
            store.close()

    def test_before_p2_is_frozen_forecasts_are_a_pilot_and_nothing_is_scored(self):
        doc = self.build()
        self.assertFalse(doc["protocol"]["frozen"])
        self.assertEqual((doc["record"]["forecast_matches"], doc["record"]["m1"]["matches"]), (3, 0))
        self.assertEqual(len(doc["recent"]), 2)                                           # still shown

    def test_the_first_forecast_counts_and_only_completed_matches_are_scored(self):
        doc = self.build({"frozen_at": "2026-11-11T07:00:00Z"})
        contract.check_any(doc)
        self.assertEqual([e["a"] for e in doc["upcoming"]], ["P5"])
        self.assertEqual(sorted(e["status"] for e in doc["recent"]), ["completed", "retired"])
        record = doc["record"]
        self.assertEqual((record["forecast_matches"], record["settled"], record["m1"]["matches"]), (3, 2, 1))
        self.assertAlmostEqual(record["m1"]["log_loss"], -math.log(0.7))               # the first forecast, not 0.9
        self.assertAlmostEqual(record["elo"]["log_loss"], -math.log(1 / (1 + 10 ** (-100 / 400))))
        self.assertTrue(doc["protocol"]["frozen"])
        self.assertEqual(doc["research"]["live_model"], "M1")
        statuses = sorted((a["status"], a["p_a"]) for a in doc["archive"])
        self.assertEqual(statuses, [("counted", 0.4), ("counted", 0.55), ("counted", 0.7), ("revision", 0.9)])
        self.assertEqual(doc["archive"][0]["p_a"], 0.9)                                     # newest first
        later = self.build({"frozen_at": "2026-11-11T09:00:00Z"})
        self.assertEqual({a["status"] for a in later["archive"]}, {"pilot", "revision"})                           # issued before the freeze
        self.assertEqual(later["record"]["m1"]["matches"], 0)

    def test_the_publisher_reads_a_copy_and_skips_a_store_being_written(self):
        work = Path(self.tmp.name) / "work"
        work.mkdir()
        doc = publish.itf_document(self.path, NOW, work)
        self.assertEqual(doc["record"]["forecast_matches"], 3)
        self.assertIsNone(publish.itf_document(Path(self.tmp.name) / "missing.sqlite", NOW, work))
        store = Store(self.path)
        with store.transaction():
            store.start_run("r3", "itf_forecast", "2026-11-11T10:00:00Z", {})
        store.close()
        self.assertIsNone(publish.itf_document(self.path, NOW, work))                 # a run is in progress


if __name__ == "__main__":
    unittest.main()

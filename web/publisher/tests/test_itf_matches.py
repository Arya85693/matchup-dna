"""The ITF match board, match pages and archive (web/publisher/itf_matches.py): the main tour's formats, built from a
read-only copy of a synthetic ITF store, with each forecast's explanation rebuilt from the frozen M1 model.

    python -m unittest web.publisher.tests.test_itf_matches
"""
import datetime
import math
import tempfile
import unittest
from pathlib import Path

from matchup_dna import itf_live as live
from matchup_dna.forecasting.store import Store
from web.publisher import contract, itf_matches
from web.publisher.readonly import open_readonly

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 11, 8, 0, tzinfo=UTC)
EXPLAINER = itf_matches.Explainer()


def place(mid, a, b, start="2026-11-11T12:00:00Z"):
    return {"tour": "ATP", "tourney_id": "fs:itf-men-singles:m15-test:20261109", "tourney_date": 20261109,
            "event": "M15 Test", "tourney_level": "15", "surface": "Clay", "round": "R32", "provider_match_id": mid,
            "start": start, "identity": ("verified", "verified"), "winner_id": a, "loser_id": b, "winner_name": "A",
            "loser_name": "B", "home_provider_id": f"h{mid}", "away_provider_id": f"a{mid}"}


def row(a, b, a_elo=1500.0, b_elo=1500.0):
    r = {f: 0 for f in live.INPUT_FIELDS}
    r.update(a_id=a, b_id=b, a_elo=a_elo, b_elo=b_elo, elo_diff=a_elo - b_elo, a_name=f"P{a}", b_name=f"P{b}",
             tour="ATP", surface="Clay", round="R32", tier=1, tourney_date=20261109, a_elo_matches=40,
             b_elo_matches=30, a_days_since=7, b_days_since=14, a_rank=310, b_rank=520, a_form=0.6, b_form=0.5,
             a_surface_matches=12, b_surface_matches=9)
    return r


def m1(r):
    """The probability the frozen M1 gives for a row, as an ITF run would store it."""
    inputs = {f: r[f] for f in live.INPUT_FIELDS}
    return float(EXPLAINER.models[r["tour"]].predict([EXPLAINER.row(inputs)])[0])


class ItfMatchFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "itf.sqlite"
        store = Store(self.path, "live")
        with store.transaction():
            store.start_run("r1", "itf_forecast", "2026-11-11T08:00:00Z", {})
            store.register_model(live.MODEL_VERSION, "itf_tournament_start", "{}", "m" * 64)
            store.register_model(live.BASELINE_VERSION, "itf_elo_only", "{}", "b" * 64)
            first = row(1, 2, 1600, 1500)
            live.issue(store, "r1", NOW, place("x1", 1, 2), first, m1(first), "m" * 64, "b" * 64)
            other = row(3, 4)
            live.issue(store, "r1", NOW, place("x2", 3, 4), other, m1(other), "m" * 64, "b" * 64)
            store.start_run("r2", "itf_forecast", "2026-11-11T09:00:00Z", {})
            revised = row(1, 2, 1700, 1500)
            live.issue(store, "r2", NOW, place("x1", 1, 2), revised, m1(revised), "m" * 64, "b" * 64)
            uid = store.match_for_alias("flashscore", "ATP", "x1")
            store.add_outcome(uid, "flashscore", "x1", "completed", 1, "6-3 6-4", 3, NOW, NOW, "r2")
            store.finish_run("r1", "ok", {})
            store.finish_run("r2", "ok", {})
        store.close()

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        store = open_readonly(self.path)
        try:
            return itf_matches.build(store, "2026-11-11T10:00:00Z", None)
        finally:
            store.close()

    def test_the_three_files_use_the_main_tour_formats(self):
        files = self.build()
        self.assertEqual(set(files), {"itf/matches.json", "itf/match-pages.json", "itf/archive.json"})
        for document in files.values():
            contract.check_any(document)
        matches = files["itf/matches.json"]["matches"]
        self.assertEqual(len(matches), 2)
        for m in matches:
            self.assertRegex(m["uid"], r"^I-[0-9a-f]{24}$")
            self.assertEqual(m["edition"]["level"], "15")                # shown as "ITF Men · M15"
            self.assertFalse(m["forecasts"]["round_aware"]["available"])
            self.assertEqual(m["forecasts"]["round_aware"]["reason_code"], "itf_no_round_aware")
        self.assertEqual(set(files["itf/match-pages.json"]["pages"]), {m["uid"] for m in matches})

    def test_a_revision_is_kept_and_the_explanation_gives_back_each_probability(self):
        files = self.build()
        uid = next(m["uid"] for m in files["itf/matches.json"]["matches"] if m["result"])
        versions = files["itf/match-pages.json"]["pages"][uid]["versions"]["tournament_start"]
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[1]["supersedes"], versions[0]["prediction_id"])
        for v in versions:
            p = v["p"][0]
            self.assertAlmostEqual(sum(c["log_odds"] for c in v["contributions"]), math.log(p / (1 - p)), places=9)
        archive = files["itf/archive.json"]["entries"]
        self.assertEqual(len(archive), 3)
        self.assertEqual(sum(e["superseded"] for e in archive), 1)

    def test_a_probability_the_model_cannot_give_back_is_refused(self):
        store = Store(self.path, "live")
        with store.transaction():
            store.start_run("r3", "itf_forecast", "2026-11-11T10:00:00Z", {})
            odd = row(5, 6, 1550, 1500)
            live.issue(store, "r3", NOW, place("x3", 5, 6), odd, 0.123, "m" * 64, "b" * 64)
            store.finish_run("r3", "ok", {})
        store.close()
        with self.assertRaises(itf_matches.ContributionError):
            self.build()


if __name__ == "__main__":
    unittest.main()

import math
import unittest
import zlib

import numpy as np

from matchup_dna import posthoc_big_match as v1
from matchup_dna import posthoc_big_match_robustness as rb


def synthetic(seed, players=60, matches=8000, clutch_sd=0.0, form_sd=0.0, tour="ATP"):
    """A small data set in the robustness module's array layout, with optional clutch and form traits."""
    rng = np.random.default_rng(seed)
    clutch, form = rng.normal(0, clutch_sd, players), rng.normal(0, form_sd, players)
    a = rng.integers(0, players, matches)
    b = (a + rng.integers(1, players, matches)) % players
    a, b = np.minimum(a, b), np.maximum(a, b)
    big = rng.random(matches) < 0.3
    z = rng.normal(0, 0.8, matches)
    truth = z + form[a] - form[b] + np.where(big, clutch[a] - clutch[b], 0.0)
    y = (rng.random(matches) < rb.sigmoid(truth)).astype(float)
    dates = rng.choice([20050101, 20150101, 20220101], matches)
    tourney = rng.integers(0, 400, matches)
    return {
        "tour": np.full(matches, tour), "big": big, "best_of": np.full(matches, 3),
        "round": np.where(big, rng.choice(["SF", "F", "QF"], matches), "R32"), "date": dates,
        "half": np.array([zlib.crc32(f"{tour}|{t}".encode()) % 2 for t in tourney]),
        "a": a, "b": b, "z": z, "y": y, "share": rb.sigmoid(truth) * 0.6 + 0.2,
        "z_wt": z, "wt_eligible": np.ones(matches, bool), "players": players,
        "tourney": tourney,
    }


def as_rows(d):
    """The same matches as version 1 row dicts."""
    return [{"tour": str(d["tour"][i]), "kind": "big" if d["big"][i] else "regular", "best_of": int(d["best_of"][i]),
             "round": str(d["round"][i]), "a": (str(d["tour"][i]), int(d["a"][i])),
             "b": (str(d["tour"][i]), int(d["b"][i])), "p_a": float(rb.sigmoid(d["z"][i])), "y": float(d["y"][i]),
             "date": int(d["date"][i]), "tourney_id": str(d["tourney"][i])} for i in range(len(d["y"]))]


class GamesTests(unittest.TestCase):
    def test_sets_and_tiebreaks(self):
        self.assertEqual(rb.games("6-4 3-6 7-6(5)"), (16, 16))
        self.assertEqual(rb.games("6-7(10) 6-3 6-4"), (18, 14))
        self.assertEqual(rb.games("6-4 2-6 7-6(3) 2-6 10-8"), (27, 30))

    def test_a_match_tiebreak_counts_as_one_game(self):
        self.assertEqual(rb.games("6-7(15) 7-6(2) [10-7]"), (14, 13))
        self.assertEqual(rb.games("6-4 5-7 [13-11]"), (12, 11))

    def test_unreadable_scores(self):
        self.assertIsNone(rb.games("W/O"))
        self.assertIsNone(rb.games(""))


class ReproductionTests(unittest.TestCase):
    """The array code must give exactly version 1's numbers on the same matches."""

    def setUp(self):
        self.d = synthetic(11, clutch_sd=0.3)
        self.rows = as_rows(self.d)
        self.mask = np.ones(len(self.d["y"]), bool)

    def test_calibration_and_spread_match_version_1(self):
        p_v1, slopes_v1 = v1.calibrate(self.rows)
        p, slopes = rb.calibrate(self.d["z"], self.d["y"], rb.groups(self.d, self.d["big"]), self.mask)
        np.testing.assert_allclose(p, p_v1, atol=1e-9)
        self.assertAlmostEqual(slopes[2][0], slopes_v1[("ATP", "big", 3)], places=10)
        for kind, chosen in (("big", self.d["big"]), ("regular", ~self.d["big"])):
            want = v1.spread(v1.player_stats(self.rows, p_v1, kind))
            got = rb.spread(*rb.totals(self.d, self.d["y"] - p, p * (1 - p), chosen))
            for key in ("players", "ratio", "trait_sd", "observed_sd", "noise_sd"):
                self.assertAlmostEqual(got[key], want[key], places=10)

    def test_persistence_test_matches_version_1(self):
        periods = ((20000101, 20101231), (20110101, 20261231))
        got = rb.period_tests(self.d, self.d["y"], self.d["z"], self.mask, periods, self.d["big"], min_n=5)
        first = [r for r in self.rows if r["date"] <= 20101231]
        second = [r for r in self.rows if r["date"] > 20101231]
        p1, _ = v1.calibrate(first)
        p2, _ = v1.calibrate(second)
        score_1, clutch_1 = v1.scores(v1.player_stats(first, p1, "big"), v1.player_stats(first, p1, "regular"))
        rng = np.random.default_rng(0)
        for key, earlier in (("big", score_1), ("clutch", clutch_1)):
            want = v1.predictive(second, p2, earlier, rng, permutations=1)
            self.assertAlmostEqual(got["forecasts"][key]["beta"], want["beta"], places=8)
            self.assertAlmostEqual(got["forecasts"][key]["log_loss_change"], want["log_loss_change"], places=10)
            self.assertEqual(got["forecasts"][key]["with_history"], want["with_history"])


class ClutchSpreadTests(unittest.TestCase):
    def test_a_clutch_trait_shows_up(self):
        d = synthetic(12, players=40, matches=40000, clutch_sd=0.5)
        mask = np.ones(len(d["y"]), bool)
        result = rb.window_tests(d, d["y"], d["z"], mask)
        self.assertGreater(result["clutch"]["ratio"], 1.5)

    def test_general_form_is_removed(self):
        d = synthetic(13, players=40, matches=40000, form_sd=0.5)
        mask = np.ones(len(d["y"]), bool)
        result = rb.window_tests(d, d["y"], d["z"], mask)
        self.assertGreater(result["spread"]["all big matches"]["ratio"], 1.5)   # form inflates the big-match spread
        self.assertLess(result["clutch"]["ratio"], 1.35)                         # but not the clutch spread


class SimulationTests(unittest.TestCase):
    def test_injected_trait_raises_the_statistics(self):
        d = synthetic(14, players=60, matches=20000)
        d["date"] = np.where(np.arange(len(d["y"])) % 2 == 0, 20150101, 20220101)
        mask = np.ones(len(d["y"]), bool)
        p, _ = rb.calibrate(d["z"], d["y"], rb.groups(d, d["big"]), mask)
        rng = np.random.default_rng(15)
        none = [rb.simulate(d, mask, p, 0.0, rng) for _ in range(5)]
        strong = [rb.simulate(d, mask, p, 0.8, rng) for _ in range(5)]
        for key in ("ratio all big matches", "clutch ratio", "forecast z big"):
            self.assertGreater(np.mean([s[key] for s in strong]), np.mean([s[key] for s in none]), key)
        self.assertGreater(np.mean([s["forecast z big"] for s in strong]), 3)


class HelperTests(unittest.TestCase):
    def test_holm(self):
        self.assertEqual(rb.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])

    def test_upper_bound_interpolates(self):
        self.assertAlmostEqual(rb.upper_bound((0.0, 0.1, 0.2), [0.5, 0.15, 0.0]), 0.1 + 0.1 * (0.10 / 0.15))
        self.assertIsNone(rb.upper_bound((0.0, 0.1), [0.5, 0.2]))

    def test_evens(self):
        self.assertAlmostEqual(rb.evens(0.0), 0.0)
        self.assertAlmostEqual(rb.evens(math.log(0.55 / 0.45)), 5.0)

    def test_tail_p(self):
        self.assertAlmostEqual(rb.tail_p(np.array([0.1, 0.2, 0.3, np.nan]), 0.25), 2 / 4)


if __name__ == "__main__":
    unittest.main()

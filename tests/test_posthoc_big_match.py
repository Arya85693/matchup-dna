import math
import unittest

import numpy as np

from matchup_dna.posthoc_big_match import (calibrate, classify, fit_one, player_stats, predictive, scores, shrunk,
                                           sigmoid, spread)


def match(round_name, level="A", tour="ATP"):
    return {"tour": tour, "tourney_level": level, "round": round_name}


def row(a, b, p_a, y, kind="big", tour="ATP", best_of=3, round_name="SF"):
    return {"tour": tour, "kind": kind, "best_of": best_of, "round": round_name, "a": (tour, a), "b": (tour, b),
            "p_a": p_a, "y": y, "date": 20150101, "tourney_id": "T"}


class ClassifyTests(unittest.TestCase):
    def test_semi_finals_and_finals_are_big_at_any_tour_level(self):
        self.assertEqual(classify(match("SF", "A")), "big")
        self.assertEqual(classify(match("F", "I", "WTA")), "big")

    def test_late_slam_and_masters_rounds(self):
        self.assertEqual(classify(match("R16", "G")), "big")
        self.assertEqual(classify(match("QF", "G")), "big")
        self.assertEqual(classify(match("R32", "G")), "regular")
        self.assertEqual(classify(match("QF", "M")), "big")
        self.assertEqual(classify(match("R16", "M")), "regular")
        self.assertEqual(classify(match("QF", "PM", "WTA")), "big")
        self.assertEqual(classify(match("QF", "A")), "regular")

    def test_finals_round_robin_is_big_and_team_events_are_left_out(self):
        self.assertEqual(classify(match("RR", "F")), "big")
        self.assertIsNone(classify(match("F", "D")))
        self.assertIsNone(classify(match("BR", "O")))
        self.assertIsNone(classify(match("SF", "M", "WTA")))


class ScoreTests(unittest.TestCase):
    def test_player_stats_and_shrinkage(self):
        rows = [row(1, 2, 0.75, 1.0), row(1, 2, 0.75, 0.0), row(1, 3, 0.5, 1.0, kind="regular")]
        stats = player_stats(rows, [r["p_a"] for r in rows], "big")
        self.assertEqual(stats[("ATP", 1)][:3], [2, 1.0, 1.5])
        self.assertEqual(stats[("ATP", 2)][:3], [2, 1.0, 0.5])
        self.assertNotIn(("ATP", 3), stats)
        self.assertAlmostEqual(shrunk(stats[("ATP", 1)], k=2), -0.5 / 4)
        self.assertEqual(shrunk(None), 0.0)

    def test_clutch_subtracts_the_regular_match_score(self):
        big = {("ATP", 1): [10, 8.0, 5.0, 2.5]}
        regular = {("ATP", 1): [10, 6.0, 5.0, 2.5]}
        score, clutch = scores(big, regular, k=10)
        self.assertAlmostEqual(score[("ATP", 1)], 3 / 20)
        self.assertAlmostEqual(clutch[("ATP", 1)], 3 / 20 - 1 / 20)


class FitTests(unittest.TestCase):
    def test_fit_one_recovers_a_slope(self):
        rng = np.random.default_rng(1)
        x = rng.normal(0, 1, 20000)
        y = (rng.random(20000) < sigmoid(1.3 * x)).astype(float)
        slope, se = fit_one(x, y)
        self.assertLess(abs(slope - 1.3), 4 * se)

    def test_calibrate_fits_each_group_separately(self):
        rng = np.random.default_rng(2)
        rows = []
        for best_of, true_slope in ((3, 1.0), (5, 1.5)):
            for _ in range(5000):
                p = rng.uniform(0.2, 0.8)
                z = math.log(p / (1 - p))
                rows.append(row(1, 2, p, float(rng.random() < sigmoid(true_slope * z)), best_of=best_of))
        _, slopes = calibrate(rows)
        self.assertAlmostEqual(slopes[("ATP", "big", 3)], 1.0, delta=0.15)
        self.assertAlmostEqual(slopes[("ATP", "big", 5)], 1.5, delta=0.2)


class SpreadTests(unittest.TestCase):
    def simulate(self, trait_sd, seed):
        rng = np.random.default_rng(seed)
        traits = rng.normal(0, trait_sd, 200)
        stats = {}
        for player, trait in enumerate(traits):
            p = np.full(40, 0.5)
            won = rng.random(40) < np.clip(p + trait, 0.01, 0.99)
            stats[player] = [40, float(won.sum()), float(p.sum()), float((p * (1 - p)).sum())]
        return spread(stats)

    def test_pure_luck_gives_a_ratio_near_one(self):
        result = self.simulate(0.0, 3)
        self.assertLess(abs(result["ratio"] - 1), 0.3)

    def test_a_real_trait_shows_up(self):
        result = self.simulate(0.12, 4)
        self.assertGreater(result["ratio"], 2)
        self.assertAlmostEqual(result["trait_sd"], 0.12, delta=0.04)


class PredictiveTests(unittest.TestCase):
    def test_a_persistent_trait_is_detected_and_noise_is_not(self):
        rng = np.random.default_rng(5)
        players = list(range(60))
        trait = {("ATP", p): rng.normal(0, 0.6) for p in players}
        rows = []
        for _ in range(6000):
            a, b = rng.choice(players, 2, replace=False)
            p = sigmoid(trait[("ATP", a)] - trait[("ATP", b)])
            rows.append(row(a, b, 0.5, float(rng.random() < p)))
        probabilities = [0.5] * len(rows)
        found = predictive(rows, probabilities, trait, rng, permutations=50)
        self.assertGreater(found["beta"], 0.5)
        self.assertLess(found["permutation_p"], 0.05)
        noise = {key: rng.normal(0, 0.6) for key in trait}
        found = predictive(rows, probabilities, noise, rng, permutations=50)
        self.assertGreater(found["permutation_p"], 0.01)


if __name__ == "__main__":
    unittest.main()

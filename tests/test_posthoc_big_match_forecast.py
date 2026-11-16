import unittest

import numpy as np

from matchup_dna import posthoc_big_match_forecast as f


def synthetic(seed=0, years=range(2000, 2016), per_year=400, players=40):
    """Random matches with a known Elo log-odds, about 15% big; outcomes drawn from sigmoid(0.8 z)."""
    rng = np.random.default_rng(seed)
    rows = []
    for year in years:
        for i in range(per_year):
            a, b = rng.choice(players, 2, replace=False)
            z = rng.normal(0, 1)
            rows.append({"tour": "ATP" if i % 2 else "WTA", "date": year * 10000 + 101, "kind": "big" if i % 7 == 0 else "regular",
                         "best_of": 3, "p_a": 1 / (1 + np.exp(-z)), "y": float(rng.random() < 1 / (1 + np.exp(-0.8 * z))),
                         "a": (int(a),), "b": (int(b),), "tourney_id": f"{year}-{i // 30}"})
    return f.arrays(rows)


class FitTests(unittest.TestCase):
    def test_slope_recovers_the_generating_value(self):
        rng = np.random.default_rng(1)
        z = rng.normal(0, 1.5, 40000)
        y = (rng.random(40000) < 1 / (1 + np.exp(-0.7 * z))).astype(float)
        slope, se = f.fit_slope(z, y)
        self.assertAlmostEqual(slope, 0.7, delta=4 * se)

    def test_weights_equal_duplicated_rows(self):
        rng = np.random.default_rng(2)
        z = rng.normal(0, 1, 500)
        y = (rng.random(500) < 0.5).astype(float)
        w = rng.integers(0, 3, 500).astype(float)
        weighted = f.fit_slope(z, y, w)[0]
        repeated = f.fit_slope(np.repeat(z, w.astype(int)), np.repeat(y, w.astype(int)))[0]
        self.assertAlmostEqual(weighted, repeated, places=8)

    def test_eb_shrinks_to_zero_without_excess_variance(self):
        mean = np.array([0.1, -0.1, 0.05, -0.05])
        shrunk, tau2 = f.eb_shrink(mean, np.full(4, 1.0), np.ones(4, dtype=bool))
        self.assertEqual(tau2, 0.0)
        self.assertTrue(np.all(shrunk == 0))

    def test_eb_weight_is_tau2_over_tau2_plus_noise(self):
        mean = np.array([1.0, -1.0, 2.0, -2.0])
        noise = np.full(4, 0.5)
        shrunk, tau2 = f.eb_shrink(mean, noise, np.ones(4, dtype=bool))
        self.assertAlmostEqual(tau2, 2.5 - 0.5)
        np.testing.assert_allclose(shrunk, mean * tau2 / (tau2 + 0.5))


class LeakageTests(unittest.TestCase):
    def test_forecasts_for_a_year_do_not_depend_on_that_year_or_later(self):
        d = synthetic()
        prob, _, _ = f.evaluate(d, f.chronological(d)[0])
        changed = synthetic()
        later = changed["year"] >= 2013
        changed["y"][later] = 1 - changed["y"][later]          # flip every result from 2013 on
        prob_changed, _, _ = f.evaluate(changed, f.chronological(changed)[0])
        before = (d["year"] >= f.FIRST_EVAL_YEAR) & (d["year"] <= 2013)
        for name in prob:
            np.testing.assert_allclose(prob[name][before], prob_changed[name][before], equal_nan=True)
        self.assertFalse(np.allclose(prob["M1"][d["year"] == 2014], prob_changed["M1"][d["year"] == 2014]))

    def test_every_model_scores_the_same_big_matches(self):
        d = synthetic()
        prob, _, _ = f.evaluate(d, f.chronological(d)[0])
        rows = (d["year"] >= f.FIRST_EVAL_YEAR) & d["big"]
        for name in prob:
            self.assertFalse(np.isnan(prob[name][rows]).any(), name)


if __name__ == "__main__":
    unittest.main()

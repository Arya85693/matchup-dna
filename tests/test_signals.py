"""Phase 5: model-against-market signals (matchup_dna.signals)."""
import unittest

import numpy as np

from matchup_dna import signals


class SignalTests(unittest.TestCase):
    def setUp(self):
        generator = np.random.default_rng(5)
        self.market = generator.uniform(0.2, 0.8, 400)
        self.model = np.clip(self.market + generator.normal(0, 0.08, 400), 0.02, 0.98)
        self.clusters = np.repeat(np.arange(40), 10)

    def test_slope_is_one_when_the_model_is_right_and_zero_when_the_market_is(self):
        b, _ = signals.information_slope(self.model, self.market, self.model, self.clusters)
        self.assertAlmostEqual(b, 1.0)
        b, _ = signals.information_slope(self.model, self.market, self.market, self.clusters)
        self.assertAlmostEqual(b, 0.0)

    def test_swapping_players_leaves_the_slope_unchanged(self):
        y = (self.model > 0.5).astype(float)
        b1, se1 = signals.information_slope(self.model, self.market, y, self.clusters)
        b2, se2 = signals.information_slope(1 - self.model, 1 - self.market, 1 - y, self.clusters)
        self.assertAlmostEqual(b1, b2)
        self.assertAlmostEqual(se1, se2)

    def test_a_blend_gives_the_model_no_weight_when_outcomes_follow_the_market(self):
        w = signals.fit_blend(self.market, self.model, self.market)
        self.assertAlmostEqual(w[0], 1.0, places=4)
        self.assertAlmostEqual(w[1], 0.0, places=4)

    def test_a_blend_is_symmetric(self):
        w = (0.9, 0.2)
        a = signals.blend(w, self.market, self.model)
        b = signals.blend(w, 1 - self.market, 1 - self.model)
        self.assertTrue(np.allclose(a, 1 - b))

    def test_market_probability_removes_the_margin(self):
        self.assertAlmostEqual(signals.market_probability(1.9, 1.9, "power"), 0.5)
        self.assertGreater(signals.market_probability(1.25, 4.0, "power"), (1 / 1.25) / (1 / 1.25 + 1 / 4.0))


if __name__ == "__main__":
    unittest.main()

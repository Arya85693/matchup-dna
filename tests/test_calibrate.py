import unittest

import numpy as np

from matchup_dna.calibrate import apply_platt, apply_temperature, fit_platt, fit_temperature
from matchup_dna.model import sigmoid


def overconfident(n=40000, shrink=0.7, seed=0):
    rng = np.random.default_rng(seed)
    z = rng.normal(0, 1.5, n)
    y = (rng.random(n) < sigmoid(shrink * z)).astype(float)
    return sigmoid(z), y


class TemperatureTests(unittest.TestCase):
    def test_recovers_the_shrink(self):
        p, y = overconfident()
        self.assertAlmostEqual(fit_temperature(p, y), 0.7, delta=0.03)

    def test_calibrated_input_gives_b_near_one(self):
        p, y = overconfident(shrink=1.0)
        self.assertAlmostEqual(fit_temperature(p, y), 1.0, delta=0.03)

    def test_b_of_one_changes_nothing_and_half_stays_half(self):
        p = np.array([0.2, 0.5, 0.9])
        np.testing.assert_allclose(apply_temperature(p, 1.0), p)
        self.assertAlmostEqual(float(apply_temperature(np.array([0.5]), 0.3)[0]), 0.5)

    def test_swapping_players_gives_one_minus(self):
        p = np.array([0.1, 0.35, 0.8])
        np.testing.assert_allclose(apply_temperature(1 - p, 0.8), 1 - apply_temperature(p, 0.8))


class PlattTests(unittest.TestCase):
    def test_intercept_near_zero_when_player_a_is_random(self):
        p, y = overconfident(seed=3)
        a, b = fit_platt(p, y)
        self.assertAlmostEqual(a, 0.0, delta=0.03)
        self.assertAlmostEqual(b, 0.7, delta=0.03)
        np.testing.assert_allclose(apply_platt(p, 0.0, b), apply_temperature(p, b))


if __name__ == "__main__":
    unittest.main()

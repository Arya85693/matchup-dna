import unittest

import numpy as np

from matchup_dna.experiment import final, keep_rule, match_log_loss, winner_probability
from matchup_dna.model import sigmoid


def validation_like(n=6000, seed=0):
    rng = np.random.default_rng(seed)
    z = rng.normal(0, 1.2, n)
    y = (rng.random(n) < sigmoid(z)).astype(float)
    rows = [{"tour": "ATP" if i % 2 else "WTA", "tourney_date": 20210104 + (i % 3) * 10000 + (i % 40)}
            for i in range(n)]
    return rows, y, z


class KeepRuleTests(unittest.TestCase):
    def test_clearly_better_model_is_kept(self):
        rows, y, z = validation_like()
        outcome = keep_rule(rows, y, sigmoid(z), sigmoid(0.3 * z))
        self.assertTrue(outcome["passed"])
        self.assertEqual(outcome["years_improved"], 3)

    def test_identical_model_is_rejected(self):
        rows, y, z = validation_like()
        self.assertFalse(keep_rule(rows, y, sigmoid(z), sigmoid(z))["passed"])

    def test_worse_on_one_tour_is_rejected(self):
        rows, y, z = validation_like()
        atp = np.array([row["tour"] == "ATP" for row in rows])
        new = np.where(atp, sigmoid(z), sigmoid(3 * z))
        self.assertFalse(keep_rule(rows, y, new, sigmoid(0.6 * z))["passed"])


class ScoringTests(unittest.TestCase):
    def test_winner_probability_and_log_loss(self):
        p, y = np.array([0.8, 0.8]), np.array([1.0, 0.0])
        np.testing.assert_allclose(winner_probability(p, y), [0.8, 0.2])
        np.testing.assert_allclose(match_log_loss(p, y), -np.log([0.8, 0.2]))


class FinalGuardTests(unittest.TestCase):
    def test_final_needs_confirm(self):
        with self.assertRaises(SystemExit):
            final("experiments/frozen_protocol.json", confirm=False)


if __name__ == "__main__":
    unittest.main()

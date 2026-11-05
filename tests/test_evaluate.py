import math
import unittest

from matchup_dna.evaluate import (
    accuracy,
    brier_score,
    calibration,
    log_loss,
    paired_log_loss_difference,
    rank_accuracy,
)
from test_stats import make_match


class MetricTests(unittest.TestCase):
    def test_log_loss(self):
        self.assertAlmostEqual(log_loss([0.5]), math.log(2))
        self.assertAlmostEqual(log_loss([0.8, 0.6]), -(math.log(0.8) + math.log(0.6)) / 2)

    def test_brier_score(self):
        self.assertAlmostEqual(brier_score([0.8, 0.6]), (0.04 + 0.16) / 2)

    def test_accuracy_counts_even_odds_as_half(self):
        self.assertAlmostEqual(accuracy([0.8, 0.4, 0.5]), 1.5 / 3)

    def test_calibration_buckets_by_favorite(self):
        rows = calibration([0.65, 0.35, 0.95, 0.5])
        self.assertEqual([(round(low, 1), count) for low, _, count, _, _ in rows], [(0.6, 2), (0.9, 1)])
        low, high, count, predicted, observed = rows[0]
        self.assertAlmostEqual(predicted, 0.65)
        self.assertAlmostEqual(observed, 0.5)

    def test_paired_difference_sign(self):
        difference, _ = paired_log_loss_difference([0.6, 0.6], [0.7, 0.8])
        self.assertLess(difference, 0)


class RankTests(unittest.TestCase):
    def test_rank_baseline_uses_matches_with_both_ranks(self):
        matches = [
            make_match(20240101, 1, 2, winner_rank=5, loser_rank=20),
            make_match(20240101, 3, 4, winner_rank=30, loser_rank=10),
            make_match(20240101, 5, 6, winner_rank=None, loser_rank=10),
        ]
        predictions = [{"match": match} for match in matches]
        result = rank_accuracy(predictions, [0.4, 0.7, 0.9])
        self.assertEqual(result["matches"], 2)
        self.assertAlmostEqual(result["rank"], 0.5)
        self.assertAlmostEqual(result["elo"], 0.5)


if __name__ == "__main__":
    unittest.main()

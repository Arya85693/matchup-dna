import unittest

from matchup_dna.posthoc_big_match import SHRINK
from matchup_dna.posthoc_big_match_players import period_scores


def row(a, b, p_a, y, kind="big"):
    return {"tour": "ATP", "kind": kind, "best_of": 3, "round": "SF", "a": ("ATP", a), "b": ("ATP", b),
            "p_a": p_a, "y": y, "date": 20150101, "tourney_id": "T"}


class PeriodScoreTests(unittest.TestCase):
    def test_counts_wins_expected_and_shrunk_scores_for_both_sides(self):
        rows = [row(1, 2, 0.6, 1.0), row(1, 2, 0.6, 1.0), row(1, 3, 0.5, 0.0, "regular")]
        found = period_scores(rows, [0.6, 0.6, 0.5])
        one, two = found[("ATP", 1)], found[("ATP", 2)]
        self.assertEqual(one["big"], 2)
        self.assertEqual(one["won"], 2.0)
        self.assertAlmostEqual(one["expected"], 1.2)
        self.assertAlmostEqual(one["score"], 0.8 / (2 + SHRINK))
        self.assertAlmostEqual(one["clutch"], 0.8 / (2 + SHRINK) - (-0.5) / (1 + SHRINK))
        self.assertEqual(two["won"], 0.0)
        self.assertAlmostEqual(two["score"], -0.8 / (2 + SHRINK))
        self.assertNotIn(("ATP", 3), found)  # regular matches only: no big-match record

    def test_values_are_plain_python_numbers_for_json(self):
        found = period_scores([row(1, 2, 0.7, 1.0)], [0.7])
        for value in found[("ATP", 1)].values():
            self.assertIn(type(value), (int, float))


if __name__ == "__main__":
    unittest.main()

import unittest

from matchup_dna.elo import (
    START_RATING,
    expected_score,
    is_rated,
    k_factor,
    run_elo,
    update_rating,
    win_probability,
)
from test_stats import make_match

FIXED_32 = ("fixed", 32)


class SingleMatchTests(unittest.TestCase):
    def test_equal_ratings_give_even_odds(self):
        self.assertEqual(expected_score(1500, 1500), 0.5)

    def test_hundred_point_favorite(self):
        self.assertAlmostEqual(expected_score(1600, 1500), 0.6401, places=4)
        self.assertAlmostEqual(expected_score(1600, 1500) + expected_score(1500, 1600), 1.0)

    def test_four_hundred_points_is_ten_to_one(self):
        self.assertAlmostEqual(expected_score(1900, 1500), 10 / 11)

    def test_update_moves_by_the_surprise(self):
        expected = expected_score(1600, 1500)
        self.assertAlmostEqual(update_rating(1600, 1, expected) - 1600, 11.52, places=2)
        self.assertAlmostEqual(update_rating(1500, 1, 1 - expected) - 1500, 20.48, places=2)

    def test_decaying_k_shrinks_with_experience(self):
        self.assertAlmostEqual(k_factor(("decaying", 250), 0), 250 / 5 ** 0.4)
        self.assertLess(k_factor(("decaying", 250), 100), k_factor(("decaying", 250), 10))


class HistoryTests(unittest.TestCase):
    def test_same_week_matches_use_start_of_week_ratings(self):
        matches = [make_match(20240101, 1, 2), make_match(20240101, 1, 3)]
        predictions, ratings = run_elo(matches, FIXED_32)
        self.assertEqual([p["winner_rating"] for p in predictions], [START_RATING, START_RATING])
        self.assertAlmostEqual(ratings[("ATP", 1)]["rating"], START_RATING + 32)
        self.assertEqual(ratings[("ATP", 1)]["played"], 2)

    def test_next_week_sees_the_update(self):
        matches = [make_match(20240108, 2, 1), make_match(20240101, 1, 3)]
        predictions, _ = run_elo(matches, FIXED_32)
        later = predictions[1]
        self.assertEqual(later["match"]["tourney_date"], 20240108)
        self.assertAlmostEqual(later["loser_rating"], START_RATING + 16)
        self.assertAlmostEqual(later["winner_rating"], START_RATING)

    def test_before_stops_at_that_week(self):
        matches = [make_match(20240101, 1, 2), make_match(20240108, 1, 3)]
        predictions, ratings = run_elo(matches, FIXED_32, before=20240108)
        self.assertEqual(len(predictions), 1)
        self.assertNotIn(("ATP", 3), ratings)

    def test_unfinished_and_best_of_1_do_not_count(self):
        matches = [
            make_match(20240101, 1, 2, score="6-3 2-0 RET"),
            make_match(20240101, 1, 2, score="W/O"),
            make_match(20240101, 1, 2, best_of=1, score="6-2"),
            make_match(20240101, 1, 1),
        ]
        self.assertFalse(any(is_rated(match) for match in matches))
        predictions, ratings = run_elo(matches, FIXED_32)
        self.assertEqual((predictions, ratings), ([], {}))

    def test_tours_are_separate_pools(self):
        matches = [make_match(20240101, 1, 2), make_match(20240108, 1, 2, tour="WTA")]
        predictions, ratings = run_elo(matches, FIXED_32)
        self.assertEqual(predictions[1]["winner_rating"], START_RATING)
        self.assertEqual(ratings[("WTA", 1)]["played"], 1)

    def test_surface_rating_moves_only_on_that_surface(self):
        matches = [make_match(20240101, 1, 2, "Clay"), make_match(20240108, 1, 2, "Hard")]
        predictions, ratings = run_elo(matches, FIXED_32)
        self.assertAlmostEqual(ratings[("ATP", 1, "Clay")]["rating"], START_RATING + 16)
        self.assertEqual(predictions[1]["winner_surface_rating"], START_RATING)
        self.assertAlmostEqual(predictions[1]["winner_rating"], START_RATING + 16)

    def test_surface_weight_zero_is_ordinary_elo(self):
        matches = [make_match(20240101, 1, 2, "Clay"), make_match(20240108, 1, 2, "Hard")]
        later = run_elo(matches, FIXED_32)[0][1]
        self.assertAlmostEqual(win_probability(later), expected_score(1516, 1484))
        self.assertAlmostEqual(win_probability(later, 0.5), expected_score(1508, 1492))

    def test_missing_surface_uses_overall_rating(self):
        matches = [make_match(20240101, 1, 2), make_match(20240108, 1, 2, surface=None)]
        later = run_elo(matches, FIXED_32)[0][1]
        self.assertIsNone(later["winner_surface_rating"])
        self.assertAlmostEqual(win_probability(later, 0.5), win_probability(later))


if __name__ == "__main__":
    unittest.main()

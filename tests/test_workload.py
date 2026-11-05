import unittest

from matchup_dna.load import match_outcome
from matchup_dna.workload import match_workload, parse_sets, recent_workload


def played(score, minutes=None, w_svpt=None, l_svpt=None, date=20250106, winner=1, loser=2, number=1):
    return {"tour": "ATP", "key": ("ATP", f"T{date}", str(number), "R32"), "tourney_date": date, "score": score,
            "outcome": match_outcome(score), "minutes": minutes, "w_svpt": w_svpt, "l_svpt": l_svpt,
            "winner_id": winner, "loser_id": loser}


class ScoreTests(unittest.TestCase):
    def test_sets_games_and_match_tiebreaks(self):
        self.assertEqual(parse_sets("6-4 7-6(5)"), [(6, 4, "set"), (7, 6, "set")])
        load = match_workload(played("6-3 3-6 [10-8]"))
        self.assertEqual((load["games"], load["sets"], load["winner_games"], load["loser_games"]), (19, 3, 10, 9))

    def test_unreadable_scores_are_unknown(self):
        self.assertIsNone(parse_sets("6-4 x-3"))
        self.assertEqual(match_workload(played("6-4 x-3"))["kind"], "unknown")
        self.assertEqual(match_workload(played(""))["kind"], "unknown")
        self.assertEqual(match_workload(played("RET"))["kind"], "unknown")


class WorkloadTests(unittest.TestCase):
    def test_completed_match(self):
        load = match_workload(played("6-4 6-4", minutes=90, w_svpt=60, l_svpt=58))
        self.assertEqual((load["kind"], load["games"], load["points"], load["minutes"]), ("played", 20, 118, 90))

    def test_walkover_is_a_genuine_zero(self):
        load = match_workload(played("W/O", minutes=None))
        self.assertEqual((load["kind"], load["minutes"], load["points"], load["games"]), ("walkover", 0, 0, 0))

    def test_retirement_is_partial(self):
        load = match_workload(played("6-2 4-4 RET", minutes=70))
        self.assertEqual((load["kind"], load["games"], load["sets"], load["minutes"]), ("partial", 16, 2, 70))

    def test_missing_values_stay_missing(self):
        load = match_workload(played("6-4 6-4"))
        self.assertIsNone(load["minutes"])
        self.assertIsNone(load["points"])
        self.assertIsNone(match_workload(played("6-4 6-4", w_svpt=60))["points"])

    def test_impossible_values_are_set_to_missing_and_flagged(self):
        load = match_workload(played("6-4 6-4", minutes=5, w_svpt=30, l_svpt=30))
        self.assertIsNone(load["minutes"])
        self.assertIsNone(load["points"])
        self.assertEqual(load["flags"], ["implausible points", "implausible minutes"])


class RecentWindowTests(unittest.TestCase):
    def test_window_uses_strictly_earlier_weeks_only(self):
        target = played("6-4 6-4", date=20250120, number=9)
        history = [
            played("6-0 6-0", date=20250105, number=1),
            played("6-4 6-4", date=20250113, number=2),
            played("6-4 6-4", date=20250120, number=3),
            played("W/O", date=20250113, number=4),
        ]
        found = recent_workload(history + [target], [target])[(target["key"], "winner")]
        self.assertEqual((found["matches"], found["games"]), (1, 20))

    def test_unknown_games_make_the_sum_unknown_and_no_matches_is_zero(self):
        target = played("6-4 6-4", date=20250120, number=9)
        history = [played("", date=20250113, number=2)]
        found = recent_workload(history + [target], [target])
        self.assertIsNone(found[(target["key"], "winner")]["games"])
        alone = recent_workload([target], [target])[(target["key"], "winner")]
        self.assertEqual((alone["matches"], alone["games"]), (0, 0))


if __name__ == "__main__":
    unittest.main()

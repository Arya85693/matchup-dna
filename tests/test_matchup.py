import json
import tempfile
import unittest
from pathlib import Path

from matchup_dna.matchup import History, expected_serve, matchup_row, profile_interval
from test_profiles import MEANS, line, played


def settings_file(directory):
    path = Path(directory) / "settings.json"
    path.write_text(json.dumps({"means": {"ATP": {k: list(v) for k, v in MEANS["ATP"].items()}},
                                "settings": {"ATP": {"half_life": None, "prior_matches": 1, "representation": "raw"}}}),
                    encoding="utf-8")
    return path


def match(winner, loser, date, number, **values):
    found = played(winner, loser, date, number=number, **values)
    found.update({"tourney_level": "A", "best_of": 3, "round": "R32", "score": "6-4 6-4", "winner_rank": 10,
                  "loser_rank": 50, "tourney_id": f"T{date}"})
    return found


class MatchupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = settings_file(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_only_matches_before_the_date_are_used(self):
        early = [match(1, 2, 20100104, 1), match(1, 3, 20100111, 2)]
        later = [match(2, 1, 20100118, 3, w=line(first_won=36, second_won=24))]
        before = History(early, "ATP", 20100118, self.settings)
        with_later = History(early + later, "ATP", 20100118, self.settings)
        row_a = matchup_row(before, 1, 2, "Hard", 3)[0]
        row_b = matchup_row(with_later, 1, 2, "Hard", 3)[0]
        self.assertEqual(row_a, row_b)
        self.assertEqual(row_a["a_rank"], 10)
        self.assertEqual(row_a["a_days_since"], 7)

    def test_swapping_players_mirrors_the_row(self):
        history = History([match(1, 2, 20100104, 1), match(3, 1, 20100111, 2)], "ATP", 20100118, self.settings)
        forward, backward = matchup_row(history, 1, 3, "Hard", 3)[0], matchup_row(history, 3, 1, "Hard", 3)[0]
        self.assertAlmostEqual(forward["elo_diff"], -backward["elo_diff"])
        self.assertAlmostEqual(forward["h2h_a"], -backward["h2h_a"])
        self.assertEqual(forward["a_serve"], backward["b_serve"])

    def test_expected_serve_and_interval(self):
        history = History([match(1, 2, 20100104, 1)], "ATP", 20100111, self.settings)
        strong = {"serve": 0.7, "return": 0.45}
        weak = {"serve": 0.6, "return": 0.35}
        self.assertAlmostEqual(expected_serve(history, strong, weak, "raw"), 0.7 - (0.35 - 0.4))
        low, high = profile_interval(0.6, 940, 60)
        self.assertLess(low, 0.6)
        self.assertGreater(high, 0.6)
        self.assertAlmostEqual(high - 0.6, 0.6 - low)


if __name__ == "__main__":
    unittest.main()

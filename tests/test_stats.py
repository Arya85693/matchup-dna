import unittest

from matchup_dna.load import DATA_DIR, load_matches, match_outcome, normalize_surface
from matchup_dna.stats import player_matches, player_record

PLAYER = ("ATP", 1)


def make_match(date, winner, loser, surface="Clay", score="6-4 6-4", best_of=3, tour="ATP", **serve):
    match = {
        "tour": tour,
        "tourney_date": date,
        "tourney_name": "Test Open",
        "round": "R32",
        "surface": surface,
        "best_of": best_of,
        "score": score,
        "outcome": match_outcome(score),
        "winner_id": winner,
        "winner_name": f"Player {winner}",
        "winner_rank": None,
        "loser_id": loser,
        "loser_name": f"Player {loser}",
        "loser_rank": None,
        "w_ace": None,
        "w_svpt": None,
        "w_first_in": None,
        "l_ace": None,
        "l_svpt": None,
        "l_first_in": None,
    }
    match.update(serve)
    return match


class OutcomeTests(unittest.TestCase):
    def test_score_markers(self):
        self.assertEqual(match_outcome("6-4 6-3"), "completed")
        self.assertEqual(match_outcome("6-2 4-4 RET"), "retired")
        self.assertEqual(match_outcome("6-2 ret"), "retired")
        self.assertEqual(match_outcome("W/O"), "walkover")
        self.assertEqual(match_outcome("Walkover"), "walkover")
        self.assertEqual(match_outcome("6-3 2-1 DEF"), "default")
        self.assertEqual(match_outcome("6-4 Def."), "default")
        self.assertEqual(match_outcome("6-4 3-1 ABD"), "abandoned")
        self.assertEqual(match_outcome("6-4 Played and abandoned"), "abandoned")
        self.assertEqual(match_outcome("6-6 Played and unfinished"), "abandoned")
        self.assertEqual(match_outcome(""), "unknown")
        self.assertEqual(match_outcome("UNK"), "unknown")
        self.assertEqual(match_outcome("&nbsp;"), "unknown")

    def test_surface_normalization(self):
        self.assertEqual(normalize_surface("clay"), "Clay")
        self.assertEqual(normalize_surface("Hard"), "Hard")
        self.assertIsNone(normalize_surface(""))


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.matches = [
            make_match(20240101, 1, 2, "Clay"),
            make_match(20240108, 3, 1, "Clay"),
            make_match(20240115, 1, 4, "Clay"),
            make_match(20240115, 1, 5, "Hard"),
            make_match(20240122, 1, 6, "Clay"),
            make_match(20240101, 1, 7, "Grass", score="6-3 2-0 RET"),
            make_match(20240101, 8, 1, "Hard", score="W/O"),
            make_match(20240101, 1, 9, "Hard", best_of=1, score="6-2"),
            make_match(20240101, 2, 3, "Clay"),
            make_match(20240101, 1, 2, "Clay", tour="WTA"),
        ]

    def test_same_week_is_excluded(self):
        record = player_record(self.matches, PLAYER, 20240115)
        self.assertEqual(record["surfaces"]["Clay"], {"wins": 1, "losses": 1})
        self.assertEqual(record["surfaces"]["Hard"], {"wins": 0, "losses": 0})

    def test_moving_the_date_adds_exactly_the_new_weeks(self):
        before = player_record(self.matches, PLAYER, 20240115)
        after = player_record(self.matches, PLAYER, 20240129)
        self.assertEqual(after["surfaces"]["Clay"]["wins"] - before["surfaces"]["Clay"]["wins"], 2)
        self.assertEqual(after["surfaces"]["Hard"]["wins"] - before["surfaces"]["Hard"]["wins"], 1)

    def test_unfinished_matches_are_counted_separately(self):
        record = player_record(self.matches, PLAYER, 20240115)
        self.assertEqual((record["wins"], record["losses"]), (1, 1))
        self.assertEqual(record["unfinished"]["retired"], {"wins": 1, "losses": 0})
        self.assertEqual(record["unfinished"]["walkover"], {"wins": 0, "losses": 1})
        self.assertEqual(record["best_of_1"], {"wins": 1, "losses": 0})

    def test_other_tour_with_same_id_is_ignored(self):
        used = player_matches(self.matches, PLAYER, 20240115)
        self.assertTrue(all(match["tour"] == "ATP" for match, _ in used))
        self.assertEqual(len(used), 5)


class ServeRateTests(unittest.TestCase):
    def test_rates_use_only_matches_with_serve_points(self):
        matches = [
            make_match(20240101, 1, 2, w_ace=5, w_svpt=50, w_first_in=30),
            make_match(20240108, 3, 1, l_ace=3, l_svpt=50, l_first_in=35),
            make_match(20240115, 1, 4),
            make_match(20240122, 1, 5, score="W/O", w_ace=0, w_svpt=0, w_first_in=0),
        ]
        record = player_record(matches, PLAYER, 20240201)
        self.assertAlmostEqual(record["ace_rate"], 8 / 100)
        self.assertAlmostEqual(record["first_serve_in"], 65 / 100)
        self.assertEqual(record["serve_points"], 100)

    def test_no_serve_data_gives_no_rate(self):
        record = player_record([make_match(20240101, 1, 2)], PLAYER, 20240201)
        self.assertIsNone(record["ace_rate"])
        self.assertIsNone(record["first_serve_in"])


@unittest.skipUnless((DATA_DIR / "atp").is_dir() and (DATA_DIR / "wta").is_dir(), "data folder not downloaded")
class DataTests(unittest.TestCase):
    def test_tour_level_match_counts(self):
        matches = load_matches()
        atp = sum(1 for match in matches if match["tour"] == "ATP")
        self.assertEqual(atp, 199_389)
        self.assertEqual(len(matches) - atp, 162_182)


if __name__ == "__main__":
    unittest.main()

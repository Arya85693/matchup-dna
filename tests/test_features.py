import unittest

from matchup_dna.elo import START_RATING, expected_score
from matchup_dna.features import LABEL, build_rows, load_split, player_a_is_winner, split_problems, split_rows
from matchup_dna.periods import TUNING_START
from test_stats import make_match


def dataset_match(date, winner, loser, number=1, level="A", **kwargs):
    match = make_match(date, winner, loser, **kwargs)
    match["key"] = (match["tour"], f"{date}-T", str(number), "R32")
    match["tourney_level"] = level
    return match


def side(row, player, field):
    return row[f"a_{field}"] if row["a_id"] == player else row[f"b_{field}"]


def flipped(match):
    swapped = dict(match)
    for field in ("id", "name", "rank"):
        swapped[f"winner_{field}"], swapped[f"loser_{field}"] = match[f"loser_{field}"], match[f"winner_{field}"]
    return swapped


def row_for(rows, player_ids):
    return next(row for row in rows if {row["a_id"], row["b_id"]} == set(player_ids))


class PreMatchTests(unittest.TestCase):
    def test_same_week_results_are_not_features(self):
        matches = [
            dataset_match(20100104, 1, 2, 1),
            dataset_match(20100104, 1, 3, 2),
            dataset_match(20100111, 1, 4, 1),
        ]
        rows = build_rows(matches)
        for row in rows[:2]:
            self.assertEqual((row["a_elo"], row["b_elo"]), (START_RATING, START_RATING))
            self.assertEqual(row["elo_probability"], 0.5)
        later = row_for(rows, (1, 4))
        player_1_elo = later["a_elo"] if later["a_id"] == 1 else later["b_elo"]
        self.assertAlmostEqual(player_1_elo, START_RATING + 32)

    def test_later_matches_do_not_change_earlier_rows(self):
        early = [dataset_match(20100104, 1, 2), dataset_match(20100111, 2, 3)]
        later = [dataset_match(20100118, 3, 1), dataset_match(20100118, 2, 1, 2, surface="Hard")]
        self.assertEqual(build_rows(early), build_rows(early + later)[:2])
        reversed_later = [flipped(match) for match in later]
        self.assertEqual(build_rows(early + later)[:2], build_rows(early + reversed_later)[:2])

    def test_flipping_the_result_changes_only_the_label(self):
        matches = [dataset_match(20100104, 1, 2), dataset_match(20100111, 1, 3), dataset_match(20100111, 2, 3, 2)]
        original = build_rows(matches)[1]
        changed = build_rows(matches[:1] + [flipped(matches[1])] + matches[2:])[1]
        self.assertEqual(original["a_id"], changed["a_id"])
        self.assertEqual(original[LABEL], 1 - changed[LABEL])
        self.assertEqual(
            {k: v for k, v in original.items() if k != LABEL},
            {k: v for k, v in changed.items() if k != LABEL},
        )

    def test_player_a_does_not_track_the_winner(self):
        matches = [dataset_match(20100104, n, n + 1000, n) for n in range(1, 201)]
        a_won = [player_a_is_winner(match) for match in matches]
        self.assertTrue(any(a_won) and not all(a_won))
        self.assertEqual(a_won, [not player_a_is_winner(flipped(match)) for match in matches])

    def test_probabilities_for_both_players_sum_to_one(self):
        matches = [dataset_match(20100104, 1, 2), dataset_match(20100111, 1, 3, surface="Grass")]
        for row in build_rows(matches):
            self.assertAlmostEqual(row["elo_probability"] + expected_score(row["b_elo"], row["a_elo"]), 1.0)
            self.assertAlmostEqual(
                row["surface_elo_probability"]
                + expected_score(row["b_surface_elo_blended"], row["a_surface_elo_blended"]),
                1.0,
            )

    def test_unrated_matches_are_left_out(self):
        matches = [
            dataset_match(20100104, 1, 2, 1, score="6-3 2-0 RET"),
            dataset_match(20100104, 1, 3, 2, score="W/O"),
            dataset_match(20100104, 1, 4, 3, best_of=1),
            dataset_match(20100104, 1, 5, 4),
        ]
        self.assertEqual([row["match_id"] for row in build_rows(matches)], ["ATP|20100104-T|4|R32"])

    def test_missing_surface_uses_overall_rating(self):
        row = build_rows([dataset_match(20100104, 1, 2), dataset_match(20100111, 1, 2, surface=None)])[1]
        self.assertIsNone(row["a_surface_elo_surface"])
        self.assertEqual(row["surface"], "")
        self.assertEqual(row["a_surface_elo_blended"], row["a_surface_elo_overall"])

    def test_ranks_follow_player_a(self):
        match = dataset_match(20100104, 1, 2, winner_rank=5, loser_rank=40)
        row = build_rows([match])[0]
        expected = (5, 40) if row["a_id"] == 1 else (40, 5)
        self.assertEqual((row["a_rank"], row["b_rank"]), expected)
        self.assertEqual(row["rank_diff"], expected[0] - expected[1])


class HistoryTests(unittest.TestCase):
    def test_days_and_form_come_from_earlier_weeks(self):
        matches = [
            dataset_match(20100104, 1, 2, 1),
            dataset_match(20100111, 1, 3, 1),
            dataset_match(20100111, 2, 4, 2),
        ]
        rows = build_rows(matches)
        first = row_for(rows, (1, 2))
        self.assertIsNone(first["a_days_since"])
        self.assertEqual((first["a_form_matches"], first["a_form"]), (0, 0.0))
        later = row_for(rows, (1, 3))
        self.assertEqual(side(later, 1, "days_since"), 7)
        self.assertEqual(side(later, 1, "form_matches"), 1)
        self.assertAlmostEqual(side(later, 1, "form"), 0.5)
        self.assertIsNone(side(later, 3, "days_since"))
        same_week = row_for(rows, (2, 4))
        self.assertAlmostEqual(side(same_week, 2, "form"), -0.5)

    def test_retirements_count_as_played_but_not_as_form(self):
        matches = [dataset_match(20100104, 5, 6, score="6-3 2-0 RET"), dataset_match(20100118, 5, 6)]
        row = build_rows(matches)[0]
        self.assertEqual(side(row, 5, "days_since"), 14)
        self.assertEqual(side(row, 5, "form_matches"), 0)

    def test_overlap_flag(self):
        slam = [dataset_match(20100104, 1, 2, level="G"), dataset_match(20100111, 1, 3)]
        self.assertEqual(build_rows(slam)[1]["overlap_flag"], 1)
        regular = [dataset_match(20100104, 1, 2), dataset_match(20100111, 1, 3)]
        self.assertEqual(build_rows(regular)[1]["overlap_flag"], 0)


class LoaderTests(unittest.TestCase):
    def test_loader_refuses_reserved(self):
        with self.assertRaises(ValueError):
            load_split("reserved")


class SplitTests(unittest.TestCase):
    def setUp(self):
        dates = (19951225, 20091228, 20100104, 20201228, 20210104, 20231225, 20240101, 20260525)
        self.matches = [dataset_match(date, 1, 2, number) for number, date in enumerate(dates)]
        self.splits = split_rows(build_rows(self.matches))

    def test_each_split_holds_only_its_dates(self):
        dates = {name: [row["tourney_date"] for row in rows] for name, rows in self.splits.items()}
        self.assertEqual(dates, {
            "train": [20100104, 20201228],
            "validation": [20210104, 20231225],
            "reserved": [20240101, 20260525],
        })
        self.assertEqual(split_problems(self.splits), [])

    def test_reserved_rows_have_no_label(self):
        self.assertTrue(all(LABEL in row for row in self.splits["train"] + self.splits["validation"]))
        self.assertFalse(any(LABEL in row for row in self.splits["reserved"]))

    def test_ratings_keep_moving_through_reserved_weeks(self):
        reserved = self.splits["reserved"]
        self.assertNotEqual(reserved[0]["elo_diff"], reserved[1]["elo_diff"])

    def test_check_catches_leaks(self):
        leaked = dict(self.splits["reserved"][0], **{LABEL: 1})
        broken = {
            "train": self.splits["train"] + [self.splits["validation"][0]],
            "validation": self.splits["validation"],
            "reserved": [leaked] + self.splits["reserved"][1:],
        }
        problems = split_problems(broken)
        self.assertTrue(any("outside train" in problem for problem in problems))
        self.assertTrue(any("in both" in problem for problem in problems))
        self.assertTrue(any("wrong label" in problem for problem in problems))

    def test_rows_outside_phase_3_cannot_be_split(self):
        with self.assertRaises(ValueError):
            split_rows(build_rows(self.matches, start=TUNING_START))


if __name__ == "__main__":
    unittest.main()

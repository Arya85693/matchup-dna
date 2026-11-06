import unittest

from matchup_dna.elo import ELO_K, expected_score, run_elo
from matchup_dna.phase4_features import HEAD_TO_HEAD_SHRINK, file_name, head_to_head, load_phase4
from test_round_aware import match


class LoaderTests(unittest.TestCase):
    def test_the_retrospective_file_needs_a_frozen_protocol(self):
        with self.assertRaises(PermissionError):
            load_phase4("retrospective")
        with self.assertRaises(ValueError):
            load_phase4("reserved")

    def test_recorded_paths_with_either_slash(self):
        self.assertEqual(file_name("results\\phase3\\train.csv"), "train.csv")
        self.assertEqual(file_name("results/phase3/validation.csv"), "validation.csv")


class HeadToHeadTests(unittest.TestCase):
    def test_only_earlier_meetings_count_and_are_shrunk(self):
        rows = [match(1, 2, "F", 1, date=20100104, tourney="A"), match(1, 2, "F", 1, date=20100104, tourney="B"),
                match(2, 1, "F", 1, date=20100111, tourney="C")]
        found = head_to_head(run_elo(rows, ELO_K)[0])
        self.assertEqual(found[rows[0]["key"]], (1, 0.0))
        self.assertEqual(found[rows[1]["key"]], (1, 0.0))
        low, value = found[rows[2]["key"]]
        expected = 2 * (1 - expected_score(1500, 1500)) / (2 + HEAD_TO_HEAD_SHRINK)
        self.assertEqual(low, 1)
        self.assertAlmostEqual(value, expected)


if __name__ == "__main__":
    unittest.main()

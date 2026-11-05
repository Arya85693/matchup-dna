import unittest

from matchup_dna.serve_stats import line_problems, serve_points_won, stat_line, to_count


def line(**values):
    base = {"ace": 5, "df": 2, "svpt": 60, "1stIn": 36, "1stWon": 27, "2ndWon": 13, "SvGms": 9, "bpSaved": 3,
            "bpFaced": 5}
    base.update(values)
    return base


class CountTests(unittest.TestCase):
    def test_blank_is_missing_never_zero(self):
        self.assertIsNone(to_count(""))
        self.assertEqual(to_count("0"), 0)
        self.assertEqual(to_count("12.0"), 12)
        self.assertEqual(to_count("1.5"), "invalid")
        self.assertEqual(to_count("x"), "invalid")

    def test_stat_line_reads_one_side(self):
        row = {f"{p}_{f}": "" for p in ("w", "l") for f in line()}
        row.update(w_svpt="60", l_svpt="55")
        self.assertEqual(stat_line(row, "w")["svpt"], 60)
        self.assertEqual(stat_line(row, "l")["svpt"], 55)
        self.assertIsNone(stat_line(row, "l")["ace"])


class RuleTests(unittest.TestCase):
    def test_a_consistent_line_has_no_problems(self):
        self.assertEqual(line_problems(line()), [])
        self.assertEqual(serve_points_won(line()), (40, 60))

    def test_each_rule(self):
        cases = {
            "serve points above zero": line(svpt=0, **{"1stIn": 0, "1stWon": 0, "2ndWon": 0, "df": 0, "ace": 0}),
            "first serves in within serve points": line(**{"1stIn": 61}),
            "first-serve points won within first serves in": line(**{"1stWon": 37}),
            "second-serve points won within second-serve points": line(**{"2ndWon": 25}),
            "double faults within second-serve points": line(df=25),
            "aces within points won on serve": line(ace=41),
            "break points saved within break points faced": line(bpSaved=6),
            "service games not negative": line(SvGms=-1),
        }
        for rule, values in cases.items():
            self.assertIn(rule, line_problems(values), rule)

    def test_missing_fields_are_reported_and_only_block_what_they_feed(self):
        partial = line(bpSaved=None, bpFaced=None)
        self.assertEqual(line_problems(partial), ["missing bpSaved", "missing bpFaced"])
        self.assertEqual(serve_points_won(partial), (40, 60))
        self.assertIsNone(serve_points_won(line(svpt=None)))
        self.assertIsNone(serve_points_won(line(**{"1stWon": 37})))

    def test_no_break_points_faced_is_valid_not_zero_percent(self):
        self.assertEqual(line_problems(line(bpSaved=0, bpFaced=0)), [])


if __name__ == "__main__":
    unittest.main()

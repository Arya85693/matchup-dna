import unittest

from matchup_dna.periods import DEVELOPMENT_END, DEVELOPMENT_START, PERIODS, period


class PeriodTests(unittest.TestCase):
    def test_boundaries(self):
        cases = {
            19671225: "warmup",
            19891231: "warmup",
            19900101: "tuning",
            20091231: "tuning",
            20100101: "train",
            20201231: "train",
            20210101: "validation",
            20231231: "validation",
            20240101: "reserved",
            20260525: "reserved",
        }
        for date, name in cases.items():
            self.assertEqual(period(date), name, date)

    def test_periods_are_contiguous_and_do_not_overlap(self):
        self.assertIsNone(PERIODS[0][1])
        self.assertIsNone(PERIODS[-1][2])
        for (_, start, end), (_, next_start, _) in zip(PERIODS, PERIODS[1:]):
            self.assertEqual(end, next_start)
            if start is not None:
                self.assertLess(start, end)

    def test_development_window_is_train_plus_validation(self):
        self.assertEqual(period(DEVELOPMENT_START), "train")
        self.assertEqual(period(DEVELOPMENT_END - 1), "validation")
        self.assertEqual(period(DEVELOPMENT_END), "reserved")


if __name__ == "__main__":
    unittest.main()

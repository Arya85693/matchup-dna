import contextlib
import io
import random
import unittest

import numpy as np

from matchup_dna.experiment import Output
from matchup_dna.model import labels, sigmoid
from matchup_dna.selection import calibration_line, forward, model_state
from test_phase4_model import random_row


def synthetic(rng, n, informative=True):
    rows = []
    for i in range(n):
        row = random_row(rng)
        row["tour"] = "ATP" if i % 2 else "WTA"
        row["tourney_date"] = 20100104 + (i % 14) * 10000 + (i % 50)
        serve_gap = np.log(row["a_serve"] / (1 - row["a_serve"])) - np.log(row["b_serve"] / (1 - row["b_serve"]))
        z = 0.004 * row["elo_diff"] + (1.5 * serve_gap if informative else 0.0)
        row["a_won"] = rng.random() < sigmoid(z)
        rows.append(row)
    return rows


class ForwardTests(unittest.TestCase):
    def test_a_real_signal_is_kept_and_noise_is_not(self):
        rng = random.Random(5)
        rows = synthetic(rng, 12000)
        train = [r for r in rows if r["tourney_date"] < 20210101]
        validation = [r for r in rows if 20210101 <= r["tourney_date"] < 20240101]
        reps = {"ATP": "raw", "WTA": "raw"}
        base = model_state(train, validation, ("rank",), reps)
        with contextlib.redirect_stdout(io.StringIO()):
            state, trail = forward(train, validation, labels(validation), base, ("serve_return", "head_to_head"),
                                   reps, Output(), "synthetic")
        self.assertEqual([group for group, outcome, _ in trail if outcome["passed"]], ["serve_return"])
        self.assertIn("serve_return", state["groups"])


class CalibrationTests(unittest.TestCase):
    def test_a_calibrated_model_has_slope_one(self):
        rng = np.random.default_rng(0)
        z = rng.normal(0, 1.5, 40000)
        y = (rng.random(40000) < sigmoid(z)).astype(float)
        intercept, slope = calibration_line(sigmoid(z), y)
        self.assertAlmostEqual(slope, 1.0, delta=0.05)
        self.assertAlmostEqual(intercept, 0.0, delta=0.05)
        _, overconfident = calibration_line(sigmoid(2 * z), y)
        self.assertAlmostEqual(overconfident, 0.5, delta=0.05)


if __name__ == "__main__":
    unittest.main()

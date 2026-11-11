"""ITF extension models and experiment: symmetry, scoring, the bootstrap, and the guards on the one-time steps."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from matchup_dna import itf_experiment as x, itf_model as m


def row(rng, i, swap=False):
    a = {"elo": rng.normal(1500, 150), "rank": rng.choice([None, int(rng.integers(50, 2000))]),
         "serve": rng.uniform(0.5, 0.7), "ret": rng.uniform(0.3, 0.5), "att": rng.choice([0.0, 500.0]),
         "days": int(rng.integers(3, 60)), "form": rng.normal(0, 0.1), "matches": int(rng.integers(0, 200))}
    b = {"elo": rng.normal(1500, 150), "rank": rng.choice([None, int(rng.integers(50, 2000))]),
         "serve": rng.uniform(0.5, 0.7), "ret": rng.uniform(0.3, 0.5), "att": rng.choice([0.0, 500.0]),
         "days": int(rng.integers(3, 60)), "form": rng.normal(0, 0.1), "matches": int(rng.integers(0, 200))}
    a["surface"], b["surface"] = a["elo"] + 20, b["elo"] - 10
    won = int(rng.random() < 1 / (1 + 10 ** ((b["elo"] - a["elo"]) / 400)))
    if swap:
        a, b, won = b, a, 1 - won
    return {"match_id": f"m{i}", "tourney_date": 20230101 + (i % 300), "tour": "ATP", "tourney_id": f"t{i // 8}",
            "surface": "Clay", "tier": int(1 + i % 2), "a_id": 1, "b_id": 2, "a_name": "A", "b_name": "B",
            "a_elo": a["elo"], "b_elo": b["elo"], "elo_diff": a["elo"] - b["elo"],
            "surface_elo_diff": a["surface"] - b["surface"], "a_rank": a["rank"], "b_rank": b["rank"],
            "a_elo_matches": a["matches"], "b_elo_matches": b["matches"], "a_surface_matches": a["matches"],
            "b_surface_matches": b["matches"], "a_days_since": a["days"], "b_days_since": b["days"],
            "a_form": a["form"], "b_form": b["form"], "a_serve_adjusted": a["serve"], "b_serve_adjusted": b["serve"],
            "a_return_adjusted": a["ret"], "b_return_adjusted": b["ret"], "a_serve": a["serve"], "b_serve": b["serve"],
            "a_return": a["ret"], "b_return": b["ret"], "a_serve_attempts": a["att"], "b_serve_attempts": b["att"],
            "a_won": won}


def rows(n=600, seed=1, swap=False):
    rng = np.random.default_rng(seed)
    return [row(rng, i, swap) for i in range(n)]


class ModelTests(unittest.TestCase):
    def test_swapping_the_players_flips_every_probability(self):
        fit = rows()
        for name in m.FITTED:
            model = m.ITFLogistic(name, l2=1.0).fit(fit)
            p, q = model.predict(rows(50, seed=2)), model.predict(rows(50, seed=2, swap=True))
            np.testing.assert_allclose(p + q, 1.0, atol=1e-12, err_msg=name)

    def test_elo_x_tier_is_centered_on_the_fitting_rows(self):
        fit = rows()
        prep = m.preprocessing(fit)
        self.assertAlmostEqual(prep["tier_mean"], 1.5)
        cols = m.columns(fit, prep)
        np.testing.assert_allclose(cols["elo_x_tier"], cols["elo_logit"] * (np.array([r["tier"] for r in fit]) - 1.5))

    def test_b1_is_the_plain_elo_probability(self):
        r = rows(5)
        np.testing.assert_allclose(m.elo_probability(r), [1 / (1 + 10 ** ((x["b_elo"] - x["a_elo"]) / 400)) for x in r])

    def test_metrics_and_calibration(self):
        found = m.metrics([0.9, 0.2, 0.6, 0.4], [1, 0, 0, 1])
        self.assertEqual(found["matches"], 4)
        self.assertAlmostEqual(found["accuracy"], 0.5)
        self.assertAlmostEqual(found["brier"], (0.01 + 0.04 + 0.36 + 0.36) / 4)
        self.assertEqual(sum(b["matches"] for b in found["calibration"]["bins"]), 4)

    def test_bootstrap_resamples_editions(self):
        same = m.paired_bootstrap([0.5] * 40, [0.5] * 40, [i // 4 for i in range(40)])
        self.assertEqual((same["mean"], same["se"], same["ci95"]), (0.0, 0.0, [0.0, 0.0]))
        better = m.paired_bootstrap([0.4] * 40, [0.5] * 40, [i // 4 for i in range(40)])
        self.assertAlmostEqual(better["mean"], -0.1)
        self.assertEqual(better["editions"], 10)
        again = m.paired_bootstrap(np.linspace(0, 1, 40), np.zeros(40), [i // 4 for i in range(40)])
        self.assertEqual(again, m.paired_bootstrap(np.linspace(0, 1, 40), np.zeros(40), [i // 4 for i in range(40)]))

    def test_choose_l2_picks_from_the_grid(self):
        best, scores = m.choose_l2(rows(), "M1", inner_start=20230200)
        self.assertIn(best, m.L2_GRID)
        self.assertEqual(set(scores), set(m.L2_GRID))


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.patches = [mock.patch.object(x, "VALIDATION", base / "validation.json"),
                        mock.patch.object(x, "HOLDOUT", base / "holdout.json"),
                        mock.patch.object(x, "PROTOCOL", base / "protocol.json"),
                        mock.patch.object(x, "DEVELOPMENT", base / "development.json")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_validation_runs_once(self):
        x.VALIDATION.write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit):
            x.validate()

    def test_the_held_out_test_needs_confirmation_the_protocol_and_a_first_run(self):
        with self.assertRaises(SystemExit):
            x.holdout(confirm=False)
        with mock.patch.object(x.itf_splits, "unsealed", return_value=False), self.assertRaises(SystemExit) as stop:
            x.holdout(confirm=True)
        self.assertIn("seal", str(stop.exception))
        x.HOLDOUT.write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit) as stop:
            x.holdout(confirm=True)
        self.assertIn("has run", str(stop.exception))

    def test_the_held_out_test_refuses_changed_code(self):
        x.PROTOCOL.write_text(json.dumps({"code_sha256": {"matchup_dna/itf_model.py": "0" * 64}}), encoding="utf-8")
        with mock.patch.object(x.itf_splits, "unsealed", return_value=True), self.assertRaises(SystemExit) as stop:
            x.holdout(confirm=True)
        self.assertIn("code differs", str(stop.exception))

    def test_freeze_refuses_twice_and_uncommitted_code(self):
        x.PROTOCOL.write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit):
            x.freeze()
        x.PROTOCOL.unlink()
        with mock.patch.object(x, "git", return_value=mock.Mock(returncode=1, stdout="")), \
                self.assertRaises(SystemExit) as stop:
            x.freeze()
        self.assertIn("commit these first", str(stop.exception))

    def test_code_hashes_cover_the_files_and_ignore_line_endings(self):
        hashes = x.code_hashes()
        self.assertEqual(set(hashes), set(x.CODE_FILES + x.UNTRACKED_INPUTS))
        path = Path(self.tmp.name) / "t.txt"
        path.write_bytes(b"a\r\nb\r\n")
        crlf = x.text_sha256(path)
        path.write_bytes(b"a\nb\n")
        self.assertEqual(crlf, x.text_sha256(path))


if __name__ == "__main__":
    unittest.main()

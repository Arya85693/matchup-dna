import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from matchup_dna import phase4_experiment as experiment


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.missing = Path(self.directory.name) / "phase4_frozen_protocol.json"

    def tearDown(self):
        self.directory.cleanup()

    def test_holdout_needs_confirm(self):
        with self.assertRaises(SystemExit):
            experiment.holdout(confirm=False)

    def test_holdout_and_retrospective_need_a_frozen_protocol(self):
        with mock.patch.object(experiment, "PROTOCOL_PATH", self.missing), \
                mock.patch.object(experiment, "FINAL_DIR", Path(self.directory.name) / "final"), \
                mock.patch.object(experiment, "RETROSPECTIVE_DIR", Path(self.directory.name) / "retro"):
            with self.assertRaises(SystemExit):
                experiment.holdout(confirm=True)
            with self.assertRaises(SystemExit):
                experiment.retrospective()

    def test_holdout_refuses_to_run_twice(self):
        final = Path(self.directory.name) / "final"
        final.mkdir()
        with mock.patch.object(experiment, "FINAL_DIR", final):
            with self.assertRaises(SystemExit):
                experiment.holdout(confirm=True)

    def test_an_uncommitted_protocol_is_refused(self):
        self.missing.write_text(json.dumps({"phase": 4, "frozen": "2026-11-06"}), encoding="utf-8")
        with mock.patch.object(experiment, "PROTOCOL_PATH", self.missing):
            with self.assertRaises(SystemExit):
                experiment.require_committed_protocol()

    def test_changed_or_missing_inputs_stop_the_frozen_procedure(self):
        protocol = {"inputs": {"results/phase4/does-not-exist.csv": "0" * 64}, "code_commit": "HEAD",
                    "code_paths": ["matchup_dna"]}
        with self.assertRaises(SystemExit):
            experiment.check_frozen_state(protocol)

    def test_freeze_refuses_uncommitted_code(self):
        with mock.patch.object(experiment, "PROTOCOL_PATH", self.missing), \
                mock.patch.object(experiment, "uncommitted_code", return_value=[" M matchup_dna/profiles.py"]):
            with self.assertRaises(SystemExit):
                experiment.freeze(dry_run=False)

    def test_an_uncommitted_or_foreign_amendment_is_refused(self):
        amendment = Path(self.directory.name) / "phase4_protocol_amendment_1.json"
        amendment.write_text(json.dumps({"amendment": 1, "amends_sha256": "0" * 64, "original_code_commit": "x",
                                         "code_commit": "y", "changed_files": []}), encoding="utf-8")
        protocol = {"code_commit": "x", "code_paths": ["matchup_dna"]}
        with mock.patch.object(experiment, "AMENDMENT_PATH", amendment):
            with self.assertRaises(SystemExit):
                experiment.frozen_code_commit(protocol)
        with mock.patch.object(experiment, "AMENDMENT_PATH", amendment), \
                mock.patch.object(experiment, "git_ok", return_value=True), \
                mock.patch.object(experiment, "PROTOCOL_PATH", amendment):
            with self.assertRaises(SystemExit):
                experiment.frozen_code_commit(protocol)

    def test_without_an_amendment_the_protocol_commit_is_used(self):
        with mock.patch.object(experiment, "AMENDMENT_PATH", Path(self.directory.name) / "none.json"):
            self.assertEqual(experiment.frozen_code_commit({"code_commit": "abc"}), ("abc", None))

    def test_freeze_never_overwrites(self):
        self.missing.write_text("{}", encoding="utf-8")
        with mock.patch.object(experiment, "PROTOCOL_PATH", self.missing):
            with self.assertRaises(SystemExit):
                experiment.freeze(dry_run=False)


class PowerTests(unittest.TestCase):
    def test_minimum_detectable_gain_scales_with_sample_size(self):
        found = experiment.minimum_detectable(0.0007, 16000, 4000)
        self.assertAlmostEqual(found["held_out_se"], 0.0014)
        self.assertAlmostEqual(found["minimum_detectable_gain"], 2.8 * 0.0014)


if __name__ == "__main__":
    unittest.main()

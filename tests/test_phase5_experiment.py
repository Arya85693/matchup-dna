"""Phase 5: the experiment's guards and its fixed slices (matchup_dna.phase5_experiment)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from matchup_dna import phase5_experiment as p5


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_the_protocol_is_never_overwritten(self):
        existing = self.root / "protocol.json"
        existing.write_text("{}", encoding="utf-8")
        with mock.patch.object(p5, "PROTOCOL_PATH", existing):
            with self.assertRaises(SystemExit):
                p5.freeze()

    def test_the_evaluation_runs_once_and_only_after_a_freeze(self):
        with mock.patch.object(p5, "EVALUATION_DIR", self.root):
            with self.assertRaises(SystemExit):
                p5.evaluate()
        with mock.patch.object(p5, "EVALUATION_DIR", self.root / "absent"), \
                mock.patch.object(p5, "PROTOCOL_PATH", self.root / "no_protocol.json"):
            with self.assertRaises(SystemExit):
                p5.evaluate()

    def test_changed_code_stops_the_evaluation(self):
        protocol = self.root / "protocol.json"
        protocol.write_text(json.dumps({"phase": 5, "frozen": "x", "code_sha256": {"matchup_dna/market.py": "old"},
                                        "inputs_sha256": {}}), encoding="utf-8")
        with mock.patch.object(p5, "EVALUATION_DIR", self.root / "absent"), \
                mock.patch.object(p5, "PROTOCOL_PATH", protocol):
            with self.assertRaises(SystemExit):
                p5.evaluate()


class SliceTests(unittest.TestCase):
    def test_slices_are_symmetric_in_the_two_players(self):
        self.assertEqual(p5.favourite_bucket(0.3), p5.favourite_bucket(0.7))
        self.assertEqual(p5.favourite_bucket(0.95), "90%+")
        self.assertEqual(p5.rank_group({"a_rank": 150, "b_rank": 12}), "better-ranked player top 20")
        self.assertEqual(p5.rank_group({"a_rank": None, "b_rank": 12}), "a rank missing")

    def test_rules_were_fixed_in_code(self):
        self.assertEqual(p5.RULES["primary"], {"probability": "Phase 4", "threshold": 0.05, "sizing": "flat",
                                               "haircut": 0.0})


if __name__ == "__main__":
    unittest.main()

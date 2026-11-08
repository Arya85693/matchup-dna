"""Phase 5: the dataset and its lock on the evaluation rows (matchup_dna.phase5_dataset)."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from matchup_dna import phase5_dataset as ds


class LockTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "dataset.csv"
        with open(self.path, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=ds.FIELDS)
            writer.writeheader()
            for split in ("development", "evaluation"):
                row = {k: "" for k in ds.FIELDS}
                row.update({"match_id": f"ATP|{split}|1|R32", "split": split, "tourney_date": "20240101",
                            "a_won": "1", "a_id": "1", "b_id": "2", "vb_id": "9", "best_of": "3", "open_a": "1.8",
                            "open_b": "2.0", "Phase 4": "0.6", "Phase 3": "0.6", "Elo": "0.6", "Surface Elo": "0.6"})
                writer.writerow(row)

    def tearDown(self):
        self.directory.cleanup()

    def test_development_rows_are_open_and_evaluation_rows_need_a_frozen_protocol(self):
        with mock.patch.object(ds, "DATASET_PATH", self.path):
            self.assertEqual([r["split"] for r in ds.load("development")], ["development"])
            with self.assertRaises(PermissionError):
                ds.load("evaluation")
            wrong = Path(self.directory.name) / "phase4.json"
            wrong.write_text(json.dumps({"phase": 4, "frozen": "2026-11-05"}), encoding="utf-8")
            with self.assertRaises(PermissionError):
                ds.load("evaluation", unseal_with=wrong)
            right = Path(self.directory.name) / "phase5.json"
            right.write_text(json.dumps({"phase": 5, "frozen": "2026-11-08"}), encoding="utf-8")
            rows = ds.load("evaluation", unseal_with=right)
        self.assertIsNone(rows[0]["close_a"])
        self.assertEqual((rows[0]["open_a"], rows[0]["a_won"]), (1.8, 1))


if __name__ == "__main__":
    unittest.main()

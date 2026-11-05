import csv
import json
import tempfile
import unittest
from pathlib import Path

from matchup_dna import tennisismylife as tml


def tml_row(tourney_date, winner_id="AAA1", loser_id="ZZZ9", tourney_id="2026-1", match_num="1", **values):
    row = {column: "" for column in tml.EXPECTED_COLUMNS}
    row.update({
        "tourney_id": tourney_id, "tourney_name": "Halle", "surface": "Grass", "tourney_level": "500",
        "tourney_date": str(tourney_date), "match_num": match_num, "best_of": "3", "round": "R32",
        "winner_id": winner_id, "winner_name": "Winner Player", "winner_rank": "5",
        "loser_id": loser_id, "loser_name": "Loser Player", "loser_rank": "40",
        "score": "6-4 6-4", "minutes": "80",
        **{f"{p}_{f}": "10" for p in ("w", "l") for f in tml.STAT_FIELDS},
    })
    row.update(values)
    return row


class SealTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.write({"2026_atp.csv": [tml_row(20260525), tml_row(20260601, match_num="2"),
                                     tml_row(20260601, winner_id="ZZZ9", loser_id="AAA1", match_num="3")]})

    def tearDown(self):
        self.directory.cleanup()

    def write(self, contents):
        for name in tml.FILES:
            rows = contents.get(name, [])
            with open(Path(self.directory.name) / name, "w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(tml.EXPECTED_COLUMNS))
                writer.writeheader()
                writer.writerows(rows)

    def test_rows_from_the_held_out_week_lose_every_outcome_column(self):
        before, after, _ = tml.load_tml(self.directory.name)
        self.assertFalse(before["sealed"])
        self.assertEqual(before["winner_id"], "AAA1")
        self.assertTrue(after["sealed"])
        for column in tml.OUTCOME_COLUMNS:
            self.assertNotIn(column, after)
        self.assertTrue(after["has_serve_stats"] and after["has_all_stats"])

    def test_sealed_player_order_does_not_depend_on_the_winner(self):
        _, a_won, b_won = tml.load_tml(self.directory.name)
        for field in ("id", "name", "rank"):
            self.assertNotEqual(a_won[f"a_{field}"], None)
        self.assertEqual((a_won["a_id"], a_won["b_id"]), ("AAA1", "ZZZ9"))
        self.assertEqual((b_won["a_id"], b_won["b_id"]), ("AAA1", "ZZZ9"))
        self.assertEqual((a_won["a_rank"], b_won["a_rank"]), ("5", "40"))
        self.assertEqual(tml.players(a_won), tml.players(b_won))

    def test_missing_statistics_are_flagged_not_revealed(self):
        self.write({"2026_atp.csv": [tml_row(20260601, w_svpt="")]})
        row = tml.load_tml(self.directory.name)[0]
        self.assertFalse(row["has_serve_stats"])
        self.assertFalse(row["has_all_stats"])

    def test_unsealing_needs_a_frozen_phase_4_protocol(self):
        with self.assertRaises(PermissionError):
            tml.load_tml(self.directory.name, unseal_with=Path(self.directory.name) / "missing.json")
        protocol = Path(self.directory.name) / "phase4.json"
        protocol.write_text(json.dumps({"phase": 4, "frozen": "2026-11-20"}), encoding="utf-8")
        self.assertEqual(tml.load_tml(self.directory.name, unseal_with=protocol)[1]["winner_id"], "AAA1")

    def test_files_with_other_columns_are_refused(self):
        with open(Path(self.directory.name) / "2025_wta.csv", "w", encoding="utf-8") as file:
            file.write(",".join(tml.EXPECTED_COLUMNS[:-1]) + "\n")
        with self.assertRaises(ValueError):
            tml.load_tml(self.directory.name)

    def test_ongoing_files_are_marked(self):
        self.write({"ongoing_tourneys.csv": [tml_row(20261102)], "wta_ongoing_tourneys.csv": [tml_row(20261103)]})
        rows = tml.load_tml(self.directory.name)
        self.assertEqual({(row["tour"], row["ongoing"]) for row in rows}, {("ATP", True), ("WTA", True)})


class EditionTests(unittest.TestCase):
    def test_edition_start_is_the_earliest_round_date(self):
        rows = [dict(tml_row(date, match_num=str(n)), tour="ATP", ongoing=False, sealed=False)
                for n, date in enumerate((20260120, 20260124, 20260201))]
        edition = tml.editions(rows)[("ATP", "2026-1")]
        self.assertEqual((edition["start"], edition["end"], edition["rows"]), (20260120, 20260201, 3))


if __name__ == "__main__":
    unittest.main()

"""Phase 5: the Valuebetennis reader (matchup_dna.valuebetennis)."""
import csv
import tempfile
import unittest
from pathlib import Path

from matchup_dna import valuebetennis as vb


def raw(**values):
    row = {column: "" for column in vb.EXPECTED_COLUMNS}
    row.update({"match_id": "1", "date": "2025-06-30 12:30:00", "tournoi": "Wimbledon - London", "tournoi_id": "777",
                "categorie": "Grand Chelem", "genre": "atp", "surface": "gazon", "tour": "4",
                "joueur1": "Jannik Sinner", "joueur1_id": "22691", "joueur2": "Luca Nardi", "joueur2_id": "500",
                "cote1_ouverture": "1.05", "cote2_ouverture": "11.0", "vainqueur_id": "22691", "score": "6-1 6-1 6-1"})
    row.update(values)
    return row


class ParseTests(unittest.TestCase):
    def test_prices_must_be_decimal_odds_above_one(self):
        self.assertEqual(vb.price("1.85"), 1.85)
        for bad in ("", " ", "1.00", "0.9", "abc", None):
            self.assertIsNone(vb.price(bad))

    def test_a_row_is_typed_and_keeps_both_timestamps_apart(self):
        row = vb.parse(raw(cote1_cloture="1.04", cote2_cloture=""))
        self.assertEqual((row["tour"], row["level"], row["surface"], row["indoor"]), ("ATP", "G", "Grass", False))
        self.assertEqual(row["open"], (1.05, 11.0))
        self.assertEqual(row["close"], (1.04, None))
        self.assertFalse(vb.has_prices(row, "close"))
        self.assertEqual((row["winner"], row["round_code"], row["midnight"]), (0, 4, False))

    def test_a_winner_who_is_neither_player_is_unknown_not_guessed(self):
        self.assertIsNone(vb.parse(raw(vainqueur_id="999"))["winner"])

    def test_indoor_surfaces_and_placeholder_times(self):
        row = vb.parse(raw(surface="dur intérieur", date="2025-11-01 00:00:00"))
        self.assertEqual((row["surface"], row["indoor"], row["midnight"]), ("Hard", True, True))

    def test_qualifying_and_pairs_are_not_tour_level_singles(self):
        self.assertTrue(vb.is_qualifying(vb.parse(raw(tour="2"))))
        self.assertFalse(vb.is_qualifying(vb.parse(raw(tour="2", categorie="ITF"))))  # codes differ below tour level
        self.assertTrue(vb.tour_level_singles(vb.parse(raw())))
        self.assertFalse(vb.tour_level_singles(vb.parse(raw(tour="3"))))
        self.assertFalse(vb.tour_level_singles(vb.parse(raw(joueur1="Krolo K./Mikrut L."))))
        self.assertFalse(vb.tour_level_singles(vb.parse(raw(categorie="Challenger"))))


class FileTests(unittest.TestCase):
    def write(self, directory, header, rows):
        with open(vb.file_path(2025, directory), "w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=header, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)

    def test_files_are_read_with_a_semicolon_and_a_byte_order_mark(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write(directory, vb.EXPECTED_COLUMNS, [raw(tournoi="Open, Paris")])
            rows = vb.load_valuebetennis(directory)
        self.assertEqual([(r["vb_id"], r["tournament"]) for r in rows], [(1, "Open, Paris")])

    def test_an_unexpected_header_stops_the_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write(directory, vb.EXPECTED_COLUMNS[:-1], [{k: v for k, v in raw().items() if k != "duree_min"}])
            with self.assertRaises(ValueError):
                vb.load_valuebetennis(Path(directory))


if __name__ == "__main__":
    unittest.main()

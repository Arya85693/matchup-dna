import csv
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from matchup_dna import tennisdata as td

SEAL_TIMESTAMP = int(datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc).timestamp())


def provider_row(match_id, timestamp, tournament="Halle ATP", tour_type="1", **values):
    row = {column: "" for column in td.EXPECTED_COLUMNS}
    row.update({
        "match_id": str(match_id), "season_year": "2026", "tour_type": tour_type, "tour_type_human": "ATP Tour",
        "date_timestamp": str(timestamp), "date_human": "", "tournament": tournament, "round": "1/16-finals",
        "surface": "grass", "surface_id": "3", "status": "FINISHED", "status_extra": "FINISHED",
        "home_name": "Sinner J.", "away_name": "Zverev A.", "home_id": "1", "away_id": "2", "winner_code": "1",
        "home_set_score": "2", "away_set_score": "0", "home_service_points_won_perc": "70",
        "away_service_points_won_perc": "60", "home_odds_match_winner": "1.4",
    })
    row.update(values)
    return row


def write_file(directory, name, rows, columns=td.EXPECTED_COLUMNS):
    with open(Path(directory) / name, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def loaded(row):
    """A row as load_provider would annotate it, without going through a file."""
    return td.annotate(dict(row), "test.csv")


class SealTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        write_file(self.directory.name, "2026-atp-season.csv", [
            provider_row(1, SEAL_TIMESTAMP - 1),
            provider_row(2, SEAL_TIMESTAMP),
        ])

    def tearDown(self):
        self.directory.cleanup()

    def test_rows_from_1_june_2026_utc_lose_outcome_odds_and_statistics(self):
        before, after = td.load_provider(self.directory.name)
        self.assertFalse(before["sealed"])
        self.assertTrue(after["sealed"])
        for column in td.SEALED_COLUMNS:
            self.assertIn(column, before)
            self.assertNotIn(column, after)
        self.assertEqual(before["winner_code"], "1")
        self.assertTrue(after["has_serve_stats"])
        self.assertEqual((after["home_id"], after["tournament"]), ("1", "Halle ATP"))

    def test_unsealing_needs_a_frozen_phase_4_protocol(self):
        with self.assertRaises(PermissionError):
            td.load_provider(self.directory.name, unseal_with=Path(self.directory.name) / "missing.json")
        phase3 = Path(self.directory.name) / "phase3.json"
        phase3.write_text(json.dumps({"frozen": "2026-11-05", "model": "logistic"}), encoding="utf-8")
        with self.assertRaises(PermissionError):
            td.load_provider(self.directory.name, unseal_with=phase3)
        phase4 = Path(self.directory.name) / "phase4.json"
        phase4.write_text(json.dumps({"phase": 4, "frozen": "2026-11-20"}), encoding="utf-8")
        after = td.load_provider(self.directory.name, unseal_with=phase4)[1]
        self.assertEqual(after["winner_code"], "1")

    def test_files_with_other_columns_are_refused(self):
        write_file(self.directory.name, "2025-atp-season.csv", [provider_row(3, 0)], td.EXPECTED_COLUMNS[:-1])
        with self.assertRaises(ValueError):
            td.load_provider(self.directory.name)

    def test_there_are_49_expected_columns(self):
        self.assertEqual(len(td.EXPECTED_COLUMNS), 49)
        self.assertEqual(len(set(td.EXPECTED_COLUMNS)), 49)


class FieldTests(unittest.TestCase):
    def test_blank_is_missing_not_zero(self):
        self.assertIsNone(td.number(""))
        self.assertIsNone(td.number("  "))
        self.assertEqual(td.number("0"), 0.0)

    def test_best_of_comes_from_the_tournament(self):
        def best(tournament, tour_type="1"):
            return td.best_of(loaded(provider_row(1, 0, tournament, tour_type)))
        self.assertEqual(best("Wimbledon ATP"), 5)
        self.assertEqual(best("Wimbledon ATP - Qualification"), 3)
        self.assertEqual(best("US Open ATP - WIC"), 3)
        self.assertEqual(best("Wimbledon WTA", "2"), 3)
        self.assertEqual(best("Halle ATP"), 3)

    def test_draw_categories(self):
        self.assertTrue(td.is_main_draw(loaded(provider_row(1, 0, "Halle ATP"))))
        self.assertFalse(td.is_main_draw(loaded(provider_row(1, 0, "Halle ATP - Qualification"))))
        self.assertFalse(td.is_main_draw(loaded(provider_row(1, 0, "US Open ATP - WIC"))))
        self.assertFalse(td.is_main_draw(loaded(provider_row(1, 0, "Lyon Chall. Men", "3"))))


class EditionTests(unittest.TestCase):
    def day(self, text):
        return int(datetime.datetime.fromisoformat(text + "T12:00:00+00:00").timestamp())

    def test_editions_split_on_gaps_and_join_play_offs(self):
        rows = [loaded(provider_row(n, self.day(day), name)) for n, day, name in (
            (1, "2026-02-06", "Davis Cup - World Group I ATP"),
            (2, "2026-02-07", "Davis Cup - World Group I ATP"),
            (3, "2026-09-12", "Davis Cup - World Group I ATP"),
            (4, "2026-11-08", "Finals - Turin ATP (indoor)"),
            (5, "2026-11-14", "Finals - Turin ATP - Play Offs (indoor)"),
        )]
        by_match = td.editions(rows)
        self.assertIs(by_match[("ATP", "1")], by_match[("ATP", "2")])
        self.assertIsNot(by_match[("ATP", "1")], by_match[("ATP", "3")])
        self.assertEqual(by_match[("ATP", "2")]["tourney_date"], 20260206)
        self.assertIs(by_match[("ATP", "4")], by_match[("ATP", "5")])
        self.assertEqual(by_match[("ATP", "5")]["tourney_date"], 20261108)

    def test_the_same_match_id_on_two_tours_is_two_matches(self):
        atp = loaded(provider_row(7, self.day("2026-03-01"), "Halle ATP"))
        wta = loaded(provider_row(7, self.day("2026-08-01"), "Berlin WTA", "2"))
        by_match = td.editions([atp, wta])
        self.assertEqual(len(by_match), 2)
        self.assertEqual(by_match[("WTA", "7")]["name"], "Berlin WTA")


if __name__ == "__main__":
    unittest.main()

"""ITF extension splits: boundaries, scope, the seal on held-out rows, and the record of input files."""
import csv
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from matchup_dna import itf_splits as s

MATCH_COLUMNS = ["tourney_id", "tourney_level", "tourney_date", "round", "winner_id", "loser_id", "score"]


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, columns)
        w.writeheader()
        w.writerows(rows)


def match(tid, level, date, rnd="R32"):
    return dict(tourney_id=tid, tourney_level=level, tourney_date=date, round=rnd, winner_id="1", loser_id="2",
                score="6-1 6-1")


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        write_csv(self.data / "atp" / "atp_matches_futures_2025.csv", MATCH_COLUMNS,
                  [match("a1", "15", "20251229"), match("a1", "15", "20251229", "R16"), match("a2", "25", "20250610")])
        write_csv(self.data / "atp" / "atp_matches_futures_2026.csv", MATCH_COLUMNS, [match("a3", "15", "20260105")])
        write_csv(self.data / "wta" / "wta_matches_qual_itf_2026.csv", MATCH_COLUMNS,
                  [match("w1", "35", "20260302"), match("w1", "35", "20260302", "Q1"), match("w2", "C", "20260302"),
                   match("w3", "G", "20260119", "Q2")])
        write_csv(self.data / "wta" / "wta_rankings_20s.csv", ["ranking_date", "rank", "player"],
                  [{"ranking_date": "20251229", "rank": "1", "player": "9"},
                   {"ranking_date": "20260105", "rank": "1", "player": "9"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_edition_falls_in_one_split_by_its_date(self):
        self.assertEqual(s.split_of("20201231"), "burn_in")
        self.assertEqual(s.split_of("20210101"), "development")
        self.assertEqual(s.split_of("20250630"), "development")  # serve statistics begin in January 2025
        self.assertEqual(s.split_of("20250701"), "validation")
        self.assertEqual(s.split_of("20251229"), "validation")   # an edition starting 29 Dec stays in 2025
        self.assertEqual(s.split_of("20260101"), "held_out")
        self.assertEqual(s.split_of("20260601"), "held_out")

    def test_scope_is_itf_main_draw_only(self):
        self.assertTrue(s.in_scope(match("x", "35", "20250303"), "WTA"))
        self.assertFalse(s.in_scope(match("x", "35", "20250303", "Q1"), "WTA"))   # ITF qualifying
        for main_draw_round in ("QF", "SF", "F", "R16", "R32", "R64"):            # "QF" is not qualifying
            self.assertTrue(s.in_scope(match("x", "25", "20230303", main_draw_round), "ATP"), main_draw_round)
        self.assertFalse(s.in_scope(match("x", "C", "20250303"), "WTA"))          # WTA 125
        self.assertFalse(s.in_scope(match("x", "G", "20250303", "Q2"), "WTA"))    # tour qualifying
        self.assertTrue(s.in_scope(match("x", "S", "20190303"), "ATP"))           # men's ITF code up to 2019
        self.assertFalse(s.in_scope(match("x", "35", "20250303"), "ATP"))

    def test_the_seal_drops_held_out_rows_from_every_file(self):
        futures = list(s.rows(self.data / "atp" / "atp_matches_futures_2026.csv", allow_held_out=False))
        ranks = list(s.rows(self.data / "wta" / "wta_rankings_20s.csv", allow_held_out=False))
        self.assertEqual(futures, [])
        self.assertEqual([r["ranking_date"] for r in ranks], ["20251229"])
        self.assertEqual(len(list(s.rows(self.data / "atp" / "atp_matches_futures_2026.csv", allow_held_out=True))), 1)

    def test_the_seal_lifts_only_for_a_committed_protocol_naming_these_splits(self):
        splits, protocol = self.data / "splits.json", self.data / "protocol.json"
        splits.write_text("{}", encoding="utf-8")
        self.assertFalse(s.unsealed(protocol, splits, is_committed=lambda p: True))          # no protocol yet
        protocol.write_text(json.dumps({"splits_sha256": "0" * 64}), encoding="utf-8")
        self.assertFalse(s.unsealed(protocol, splits, is_committed=lambda p: True))          # names other splits
        protocol.write_text(json.dumps({"splits_sha256": s.sha256(splits)}), encoding="utf-8")
        self.assertFalse(s.unsealed(protocol, splits, is_committed=lambda p: False))         # not committed
        self.assertTrue(s.unsealed(protocol, splits, is_committed=lambda p: True))

    def test_counts_cover_scope_rows_by_split(self):
        c = s.counts(self.data)
        self.assertEqual(c["ATP"]["validation"], {"matches": 2, "editions": 1, "levels": {"15": 2}})
        self.assertEqual(c["ATP"]["development"], {"matches": 1, "editions": 1, "levels": {"25": 1}})
        self.assertEqual(c["ATP"]["held_out"]["matches"], 1)
        self.assertEqual(c["WTA"]["held_out"], {"matches": 1, "editions": 1, "levels": {"35": 1}})
        self.assertEqual(s.last_held_out_date(self.data), 20260302)

    def test_the_record_is_written_once_and_check_finds_any_change(self):
        path = self.data / "splits.json"
        s.write(path, self.data)
        with self.assertRaises(SystemExit):
            s.write(path, self.data)
        self.assertEqual(s.check(path, self.data), [])
        with open(self.data / "atp" / "atp_matches_futures_2026.csv", "a", encoding="utf-8") as f:
            f.write("a4,15,20260112,R32,1,2,6-0 6-0\n")
        write_csv(self.data / "atp" / "atp_matches_futures_2027.csv", MATCH_COLUMNS, [])
        self.assertEqual(s.check(path, self.data),
                         ["changed: atp/atp_matches_futures_2026.csv", "added: atp/atp_matches_futures_2027.csv"])

    def test_a_correction_keeps_the_dates_lists_itself_and_stops_once_a_protocol_exists(self):
        path, protocol = self.data / "splits.json", self.data / "protocol.json"
        s.write(path, self.data)
        first = s.sha256(path)
        with self.assertRaises(SystemExit):
            s.correct("", path, self.data, protocol)                        # a reason is required
        s.correct("scope defect", path, self.data, protocol)
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["revision"], 2)
        self.assertEqual(saved["corrections"][0]["replaces_sha256"], first)
        self.assertEqual(saved["corrections"][0]["reason"], "scope defect")
        self.assertNotIn("replaced_splits", saved["corrections"][0])
        protocol.write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit):
            s.correct("another", path, self.data, protocol)

    def test_moving_the_dates_needs_the_explicit_flag_and_records_the_old_dates(self):
        path, protocol = self.data / "splits.json", self.data / "protocol.json"
        old = (("burn_in", None, 20201231), ("development", 20210101, 20231231),
               ("validation", 20240101, 20241231), ("held_out", 20250101, None))
        with mock.patch.object(s, "SPLITS", old):
            s.write(path, self.data)
        with self.assertRaises(SystemExit):
            s.correct("re-split", path, self.data, protocol)                 # dates differ, no flag
        s.correct("re-split around serve data", path, self.data, protocol, move_dates=True)
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["splits"][3], {"name": "held_out", "first": 20260101, "last": None})
        self.assertEqual(saved["corrections"][0]["replaced_splits"][3]["first"], 20250101)


if __name__ == "__main__":
    unittest.main()

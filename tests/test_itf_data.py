"""ITF extension data: the unmarked-retirement rule, tiers, the slim record and the sealed load."""
import csv
import tempfile
import unittest
from pathlib import Path

from matchup_dna import itf_data as d
from matchup_dna import itf_splits

COLUMNS = ["tourney_id", "tourney_name", "surface", "draw_size", "tourney_level", "tourney_date", "match_num",
           "winner_id", "winner_seed", "winner_entry", "winner_name", "winner_hand", "winner_ht", "winner_ioc",
           "winner_age", "loser_id", "loser_seed", "loser_entry", "loser_name", "loser_hand", "loser_ht", "loser_ioc",
           "loser_age", "score", "best_of", "round", "minutes", "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon",
           "w_2ndWon", "w_SvGms", "w_bpSaved", "w_bpFaced", "l_ace", "l_df", "l_svpt", "l_1stIn", "l_1stWon",
           "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced", "winner_rank", "winner_rank_points", "loser_rank",
           "loser_rank_points"]


def row(**changes):
    values = {c: "" for c in COLUMNS}
    values.update(tourney_id="2025-X", tourney_name="M15 X", surface="Clay", draw_size="32", tourney_level="15",
                  tourney_date="20250303", match_num="1", winner_id="1", winner_name="Ann One", loser_id="2",
                  loser_name="Bea Two", score="6-2 6-3", best_of="3", round="R32", winner_rank="400", loser_rank="")
    values.update(changes)
    return values


def stats(**extra):
    line = {"w_svpt": "60", "w_1stIn": "36", "w_1stWon": "26", "w_2ndWon": "12", "w_SvGms": "9", "w_ace": "3",
            "w_df": "2", "w_bpSaved": "2", "w_bpFaced": "3", "l_svpt": "58", "l_1stIn": "33", "l_1stWon": "20",
            "l_2ndWon": "10", "l_SvGms": "9", "l_ace": "1", "l_df": "4", "l_bpSaved": "4", "l_bpFaced": "8"}
    line.update(extra)
    return line


class OutcomeRuleTests(unittest.TestCase):
    def outcome(self, score, family="itf"):
        m = d.to_match(row(score=score), "ATP", family)
        return m["outcome"], m["outcome_note"]

    def test_a_partial_score_written_as_finished_is_a_retirement(self):
        self.assertEqual(self.outcome("6-2 0-0"), ("retired", d.UNMARKED_RETIREMENT))
        self.assertEqual(self.outcome("6-2 3-0"), ("retired", d.UNMARKED_RETIREMENT))   # "3-0" is not a set won
        self.assertEqual(self.outcome("4-3"), ("retired", d.UNMARKED_RETIREMENT))

    def test_finished_matches_are_unchanged(self):
        for score in ("6-2 6-3", "7-6(5) 3-6 7-5", "6-4 3-6 [10-8]", "7-5 6-7(2) 6-4", "6-0 4-6 8-6"):
            self.assertEqual(self.outcome(score), ("completed", None), score)

    def test_marked_endings_keep_their_outcome(self):
        self.assertEqual(self.outcome("6-2 1-0 RET")[0], "retired")
        self.assertEqual(self.outcome("W/O")[0], "walkover")
        self.assertIsNone(self.outcome("6-2 1-0 RET")[1])

    def test_the_rule_is_for_the_itf_files_only(self):
        # main-tour short-set events (first to 4 games) are finished matches
        self.assertEqual(self.outcome("4-1 4-2 4-2", family="main"), ("completed", None))
        self.assertEqual(self.outcome("6-2 0-0", family="challenger_qualifying"), ("completed", None))

    def test_set_won(self):
        self.assertTrue(d.set_won_by_winner(6, 4, "set"))
        self.assertTrue(d.set_won_by_winner(7, 6, "set"))
        self.assertTrue(d.set_won_by_winner(8, 6, "set"))
        self.assertFalse(d.set_won_by_winner(6, 5, "set"))
        self.assertFalse(d.set_won_by_winner(5, 3, "set"))
        self.assertTrue(d.set_won_by_winner(10, 8, "match tiebreak"))
        self.assertFalse(d.set_won_by_winner(9, 7, "match tiebreak"))


class RecordTests(unittest.TestCase):
    def test_tiers_follow_the_field_strength_mapping(self):
        tiers = {(tour, level): d.to_match(row(tourney_level=level), tour, "itf")["tier"]
                 for tour, level in (("ATP", "15"), ("ATP", "25"), ("WTA", "10"), ("WTA", "25"), ("WTA", "35"),
                                     ("WTA", "40"), ("WTA", "50"), ("WTA", "60"), ("WTA", "75"), ("WTA", "80"),
                                     ("WTA", "100"))}
        self.assertEqual(tiers, {("ATP", "15"): 1, ("ATP", "25"): 2, ("WTA", "10"): 1, ("WTA", "25"): 2,
                                 ("WTA", "35"): 2, ("WTA", "40"): 3, ("WTA", "50"): 3, ("WTA", "60"): 4,
                                 ("WTA", "75"): 4, ("WTA", "80"): 4, ("WTA", "100"): 5})
        self.assertIsNone(d.to_match(row(tourney_level="S", tourney_date="20180101"), "ATP", "itf")["tier"])
        self.assertIsNone(d.to_match(row(tourney_level="C"), "WTA", "itf")["tier"])      # WTA 125, not scored

    def test_the_record_is_slim(self):
        m = d.to_match(row(**stats()), "ATP", "itf")
        self.assertEqual(m["key"][-1], "itf")
        self.assertTrue(m["itf_scope"])
        self.assertEqual(m["stats"]["w"]["svpt"], 60)
        self.assertEqual((m["winner_rank"], m["loser_rank"]), (400, None))
        self.assertNotIn("score", m)
        old = d.to_match(row(tourney_date="20140106", **stats()), "ATP", "itf")
        self.assertNotIn("stats", old)                                   # before 2015
        other = d.to_match(row(tourney_level="A"), "ATP", "main")
        self.assertFalse(other["itf_scope"])
        self.assertEqual(other["winner_name"], "")                       # names only for scored matches

    def test_families(self):
        self.assertEqual(d.family_of("atp_matches_futures_2025.csv"), "itf")
        self.assertEqual(d.family_of("wta_matches_qual_itf_2025.csv"), "itf")
        self.assertEqual(d.family_of("atp_matches_qual_chall_2025.csv"), "challenger_qualifying")
        self.assertEqual(d.family_of("wta_matches_2025.csv"), "main")
        self.assertIsNone(d.family_of("atp_matches_doubles_2019.csv"))
        self.assertIsNone(d.family_of("atp_rankings_20s.csv"))


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.write("atp/atp_matches_futures_2025.csv", [row(), row(match_num="2", round="QF")])
        self.write("atp/atp_matches_futures_2026.csv", [row(tourney_date="20260105", tourney_id="2026-X")])
        self.write("atp/atp_matches_2025.csv", [row(tourney_level="A", tourney_id="2025-A")])
        self.write("wta/wta_matches_qual_itf_2025.csv", [row(tourney_level="35"), row(tourney_level="C", match_num="9")])

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, rows):
        path = self.data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, COLUMNS)
            w.writeheader()
            w.writerows(rows)

    def test_the_sealed_load_never_returns_held_out_rows(self):
        matches = d.load(self.data, allow_held_out=False)
        self.assertEqual(len(matches), 5)
        self.assertTrue(all(m["tourney_date"] < itf_splits.HELD_OUT_START for m in matches))
        self.assertEqual(len(d.load(self.data, allow_held_out=True)), 6)

    def test_scope_and_filters(self):
        matches = d.load(self.data, allow_held_out=False)
        self.assertEqual(len(d.scope_matches(matches)), 3)                # two ATP ITF, one W35; not the 125 or main
        self.assertEqual(len(d.load(self.data, allow_held_out=False, tours=("WTA",))), 2)
        self.assertEqual(len(d.load(self.data, allow_held_out=False, families=("main",))), 1)
        self.assertEqual(len(d.load(self.data, allow_held_out=False, since=20990101)), 0)

    def test_an_exact_repeat_counts_once(self):
        self.write("wta/wta_matches_qual_itf_2024.csv", [row(tourney_level="C", round="Q1", tourney_date="20240101")] * 2)
        matches = d.load(self.data, allow_held_out=False)
        self.assertEqual(len(matches), 6)
        self.assertEqual(d.LOAD_REPORT["exact_repeats"], {("WTA", "itf", False): 1})

    def test_a_repeated_key_stops_the_load(self):
        self.write("atp/atp_matches_futures_2024.csv", [row(tourney_date="20240101")])   # same id, number, round
        with self.assertRaises(SystemExit):
            d.load(self.data, allow_held_out=False)


if __name__ == "__main__":
    unittest.main()

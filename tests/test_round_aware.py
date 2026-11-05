import copy
import math
import unittest

from matchup_dna.elo import ELO_K, SURFACE_ELO_K, expected_score, run_elo
from matchup_dna.load import match_outcome
from matchup_dna.merge import combine, provider_only_id, resolve, tml_match
from matchup_dna.round_aware import LN10_OVER_400, differences, round_aware_features

WEEK = 20250106


def match(winner, loser, round_name, number, score="6-4 6-4", date=WEEK, tourney="T1", level="A", draw="8",
          minutes=90, svpt=(60, 60), tour="ATP", source="sackmann", surface="Hard"):
    return {
        "tour": tour, "key": (tour, tourney, str(number), round_name), "tourney_id": tourney,
        "tourney_name": "Test Open", "tourney_level": level, "tourney_date": date, "match_num": str(number),
        "surface": surface, "round": round_name, "best_of": 3, "score": score, "outcome": match_outcome(score),
        "winner_id": winner, "winner_name": f"P{winner}", "winner_rank": None, "loser_id": loser,
        "loser_name": f"P{loser}", "loser_rank": None, "w_ace": None, "w_svpt": svpt[0], "w_first_in": None,
        "l_ace": None, "l_svpt": svpt[1], "l_first_in": None, "minutes": minutes, "draw_size": draw,
        "winner_entry": "", "loser_entry": "", "source": source,
    }


def eight_draw(changes=None):
    """Players 1-8. 1 beats 2, 3 beats 4, 5 beats 6, 7 beats 8; 1 beats 3, 5 beats 7; 1 beats 5 in the final."""
    rows = [
        match(1, 2, "QF", 1, "6-4 6-4"), match(3, 4, "QF", 2, "7-6(5) 6-7(3) 6-3", minutes=150, svpt=(120, 118)),
        match(5, 6, "QF", 3, "6-1 6-1", minutes=55), match(7, 8, "QF", 4, "6-3 6-3"),
        match(1, 3, "SF", 5, "6-2 6-2", minutes=70), match(5, 7, "SF", 6, "4-6 7-5 7-6(4)", minutes=170,
                                                                   svpt=(115, 110)),
        match(1, 5, "F", 7, "6-3 6-4"),
    ]
    for number, values in (changes or {}).items():
        rows[number].update(values)
        rows[number]["outcome"] = match_outcome(rows[number]["score"])
    return rows


def features(matches):
    return round_aware_features(matches, run_elo(matches, ELO_K), run_elo(matches, SURFACE_ELO_K))


def side(found, key, player, matches):
    target = next(m for m in matches if m["key"] == key)
    return found[key]["winner" if target["winner_id"] == player else "loser"]


class ChronologyTests(unittest.TestCase):
    def test_a_semifinal_never_uses_its_own_result(self):
        rows = eight_draw()
        semi = rows[5]["key"]
        before = features(rows)
        changed = eight_draw({5: {"score": "7-6(5) 7-6(5)", "minutes": 300, "w_svpt": 120, "l_svpt": 118}})
        after = features(changed)
        self.assertEqual(before[semi], after[semi])
        self.assertEqual(side(before, semi, 5, rows)["games"], 14)
        self.assertEqual(side(before, semi, 7, rows)["games"], 18)

    def test_a_final_uses_every_earlier_completed_round(self):
        rows = eight_draw()
        final = side(features(rows), rows[6]["key"], 5, rows)
        self.assertEqual(final["matches"], 2)
        self.assertEqual(final["games"], 14 + 35)
        self.assertEqual(final["minutes"], 55 + 170)
        self.assertEqual(final["points"], 120 + 225)

    def test_later_results_never_change_an_earlier_prediction(self):
        rows = eight_draw()
        before = features(rows)
        swapped_final = eight_draw({6: {"winner_id": 5, "loser_id": 1, "score": "7-6(1) 7-6(1)"}})
        after = features(swapped_final)
        for row in rows[:6]:
            self.assertEqual(before[row["key"]], after[row["key"]])

    def test_missing_duration_is_missing_not_zero(self):
        rows = eight_draw({2: {"minutes": None}})
        final = side(features(rows), rows[6]["key"], 5, rows)
        self.assertIsNone(final["minutes"])
        self.assertEqual(final["games"], 49)

    def test_walkovers_add_no_court_time(self):
        rows = eight_draw({2: {"score": "W/O", "minutes": None, "w_svpt": None, "l_svpt": None}})
        final = side(features(rows), rows[6]["key"], 5, rows)
        self.assertEqual((final["walkovers"], final["matches"]), (1, 1))
        self.assertEqual((final["games"], final["minutes"]), (35, 170))
        self.assertEqual(final["faced"], 1)

    def test_retirements_count_what_was_played_and_are_marked(self):
        rows = eight_draw({2: {"score": "6-1 2-0 RET", "minutes": 40}})
        final = side(features(rows), rows[6]["key"], 5, rows)
        self.assertEqual((final["partial"], final["games"], final["minutes"]), (1, 9 + 35, 40 + 170))

    def test_a_gap_in_earlier_rounds_makes_the_match_ineligible(self):
        rows = eight_draw()
        without_semi = [m for m in rows if m["key"] != rows[4]["key"]]
        found = features(without_semi)
        self.assertEqual(found[rows[6]["key"]]["reason"], "gap in earlier rounds")
        # A full first round (4 quarterfinals for 2 semifinals) has no byes, so a semifinalist with no
        # quarterfinal is a missing record, not a bye.
        stranger = rows[:4] + [match(9, 3, "SF", 5), match(5, 7, "SF", 6), match(9, 5, "F", 7)]
        found = features(stranger)
        self.assertEqual(found[stranger[4]["key"]]["reason"], "first round missing")

    def test_byes_are_read_from_the_draw_structure(self):
        # Three quarterfinals feed two semifinals, so one semifinalist had a bye, whatever draw_size says.
        rows = eight_draw()[1:]
        found = features(rows)
        semi = next(m for m in rows if m["round"] == "SF" and 1 in (m["winner_id"], m["loser_id"]))
        self.assertTrue(found[semi["key"]]["eligible"])
        bye = side(found, semi["key"], 1, rows)
        self.assertEqual((bye["matches"], bye["games"], bye["walkovers"]), (0, 0, 0))

    def test_uncertain_formats_are_never_ordered(self):
        team = eight_draw({n: {"tourney_level": "D"} for n in range(7)})
        self.assertTrue(all(v["reason"] == "team event" for v in features(team).values()))
        bronze = eight_draw() + [match(3, 7, "BR", 8)]
        self.assertTrue(all(v["reason"] == "unordered round" for v in features(bronze).values()))
        twice = eight_draw() + [match(1, 9, "QF", 9)]
        self.assertTrue(all(v["reason"] == "player twice in one round" for v in features(twice).values()))
        round_robin = [match(1, 2, "RR", 1), match(3, 4, "RR", 2), match(1, 3, "RR", 3), match(2, 4, "RR", 4),
                       match(1, 4, "SF", 5), match(3, 2, "SF", 6), match(1, 3, "F", 7)]
        found = features(round_robin)
        self.assertEqual(found[round_robin[0]["key"]]["reason"], "round-robin match")
        final = side(found, round_robin[6]["key"], 1, round_robin)
        self.assertTrue(found[round_robin[6]["key"]]["eligible"])
        self.assertEqual(final["matches"], 3)


class RoundAwareEloTests(unittest.TestCase):
    def test_canonical_ratings_are_untouched(self):
        rows = eight_draw()
        elo_run, surface_run = run_elo(rows, ELO_K), run_elo(rows, SURFACE_ELO_K)
        frozen = copy.deepcopy((elo_run[1], surface_run[1], [dict(p, match=None) for p in elo_run[0]]))
        round_aware_features(rows, elo_run, surface_run)
        self.assertEqual(frozen, (elo_run[1], surface_run[1], [dict(p, match=None) for p in elo_run[0]]))

    def test_each_earlier_match_moves_the_temporary_rating_once(self):
        rows = eight_draw()
        found = features(rows)
        first = 32 * (1 - expected_score(1500, 1500))
        semi = side(found, rows[4]["key"], 1, rows)
        self.assertAlmostEqual(semi["elo_shift"], first)
        second = 32 * (1 - expected_score(1500 + first, 1500 + first))
        final = side(found, rows[6]["key"], 1, rows)
        self.assertAlmostEqual(final["elo_shift"], first + second)
        self.assertEqual(side(found, rows[0]["key"], 1, rows)["elo_shift"], 0.0)

    def test_walkovers_and_retirements_do_not_move_ratings(self):
        rows = eight_draw({2: {"score": "W/O"}})
        final = side(features(rows), rows[6]["key"], 5, rows)
        semi_only = 32 * (1 - expected_score(1500, 1500 + 32 * (1 - expected_score(1500, 1500))))
        self.assertAlmostEqual(final["elo_shift"], semi_only)


class DifferenceTests(unittest.TestCase):
    def test_swapping_players_negates_every_difference(self):
        rows = eight_draw()
        found = features(rows)
        final = found[rows[6]["key"]]
        forward = differences(final["winner"], final["loser"])
        backward = differences(final["loser"], final["winner"])
        for name, value in forward.items():
            self.assertAlmostEqual(value, -backward[name], msg=name)
        self.assertAlmostEqual(forward["ra_log_games_diff"], math.log1p(36) - math.log1p(49))

    def test_route_difficulty_uses_start_of_week_ratings(self):
        history = [match(5, 9, "F", 1, date=20241230, tourney="T0")]
        rows = history + eight_draw()
        found = features(rows)
        final = side(found, rows[-1]["key"], 1, rows)
        rating_5 = 1500 + 32 * (1 - expected_score(1500, 1500))
        self.assertAlmostEqual(final["route_relative_elo"], ((1500 - 1500) + (1500 - 1500)) / 2)
        self.assertAlmostEqual(final["max_opponent_elo"], 1500)
        player_5 = side(found, rows[-1]["key"], 5, rows)
        self.assertAlmostEqual(player_5["route_relative_elo"], 1500 - rating_5)


class MergeTests(unittest.TestCase):
    def test_a_match_in_two_sources_contributes_workload_once(self):
        rows = eight_draw({2: {"minutes": None}})
        tml_copy = dict(rows[2], key=("ATP", "TML-T1", "3", "QF"), minutes=55, source="tml")
        merged, report = combine(rows, [(tml_copy, rows[2], True)])
        self.assertEqual(report["linked to Sackmann"], 1)
        self.assertEqual(len(merged), len(rows))
        final = side(features(merged), rows[6]["key"], 5, merged)
        self.assertEqual((final["matches"], final["minutes"]), (2, 55 + 170))
        self.assertIsNone(rows[2]["minutes"])

    def test_duplicates_across_sources_stop_the_build(self):
        rows = eight_draw()
        late = [dict(m, tourney_date=20260608) for m in rows]
        copy_from_tml = dict(late[2], key=("ATP", "TML-T1", "3", "QF"), source="tml")
        with self.assertRaises(ValueError):
            combine(late, [(copy_from_tml, None, None)])

    def test_unlinked_rows_in_sackmann_weeks_are_dropped(self):
        rows = eight_draw()
        extra = dict(rows[0], key=("ATP", "TML-X", "1", "QF"), winner_id=50, loser_id=51, source="tml")
        merged, report = combine(rows, [(extra, None, None)])
        self.assertEqual(len(merged), len(rows))
        self.assertEqual(report["unlinked, in Sackmann's weeks: dropped"], 1)

    def test_player_ids_are_reconciled_through_validated_links(self):
        links = {("ATP", "CD85"): 104000}
        self.assertEqual(resolve("tml", "ATP", "CD85", links), 104000)
        unknown = resolve("tml", "ATP", "ZZ99", links)
        self.assertLess(unknown, 0)
        self.assertEqual(unknown, provider_only_id("tml", "ATP", "ZZ99"))
        self.assertNotEqual(unknown, provider_only_id("tennisdata", "ATP", "ZZ99"))
        self.assertNotEqual(provider_only_id("tml", "ATP", "ZZ99"), provider_only_id("tml", "WTA", "ZZ99"))

    def test_sealed_rows_cannot_become_matches(self):
        with self.assertRaises(PermissionError):
            tml_match({"sealed": True, "a_id": "CD85", "b_id": "ZZ99", "tour": "ATP"}, {}, 20260608)


if __name__ == "__main__":
    unittest.main()

"""ITF extension ratings: Phase 2's replay reproduced exactly, and the three options."""
import math
import unittest

from matchup_dna import elo, itf_ratings as r
from itf_fixtures import matches


class EquivalenceTests(unittest.TestCase):
    def test_with_no_options_it_is_phase_2s_replay(self):
        history = matches(seed=3)
        for k_rule in (elo.ELO_K, elo.SURFACE_ELO_K, ("decaying", 250)):
            ours, our_ratings = r.run_elo(history, k_rule)
            theirs, their_ratings = elo.run_elo(history, k_rule)
            self.assertEqual(our_ratings, their_ratings)
            self.assertEqual(len(ours), len(theirs))
            for a, b in zip(ours, theirs):
                self.assertIs(a["match"], b["match"])
                self.assertEqual({k: v for k, v in a.items() if k != "match"}, {k: v for k, v in b.items() if k != "match"})

    def test_before_stops_like_phase_2(self):
        history = matches(seed=4)
        cut = sorted({m["tourney_date"] for m in history})[20]
        self.assertEqual(r.run_elo(history, before=cut)[1], elo.run_elo(history, before=cut)[1])


class OptionTests(unittest.TestCase):
    def test_matches_that_do_not_update_are_predicted_but_move_nothing(self):
        history = matches(seed=5)
        main_only, _ = r.run_elo(history, updates=lambda m: m["family"] == "main")
        reference, _ = elo.run_elo([m for m in history if m["family"] == "main"])
        by_key = {p["match"]["key"]: p for p in main_only}
        self.assertEqual(len(main_only), sum(elo.is_rated(m) for m in history))     # every rated match predicted
        for p in reference:                                                          # ratings as if ITF absent
            self.assertEqual(by_key[p["match"]["key"]]["winner_rating"], p["winner_rating"])
            self.assertEqual(by_key[p["match"]["key"]]["loser_rating"], p["loser_rating"])

    def test_keep_filters_predictions_without_changing_them(self):
        history = matches(seed=6)
        everything, ratings = r.run_elo(history)
        some, same_ratings = r.run_elo(history, keep=lambda m: m["family"] == "itf")
        self.assertEqual(ratings, same_ratings)
        self.assertEqual([p["match"]["key"] for p in some],
                         [p["match"]["key"] for p in everything if p["match"]["family"] == "itf"])

    def test_rank_start(self):
        match = {"winner_rank": 1000, "loser_rank": None}
        self.assertEqual(r.rank_start(match, "winner"), 1500)
        self.assertAlmostEqual(r.rank_start(match, "loser"), 1500 + 100 * math.log(1000 / 2000))
        self.assertEqual(r.rank_start({"winner_rank": 1}, "winner"), 1900)           # clipped
        self.assertEqual(r.rank_start({"winner_rank": 10 ** 6}, "winner"), 1100)

    def test_a_first_rating_is_fixed_when_first_seen(self):
        history = matches(seed=8, players=6)
        predictions, ratings = r.run_elo(history, start_rating=r.rank_start)
        first = {}
        for p in predictions:
            for side in ("winner", "loser"):
                pid = (p["match"]["tour"], p["match"][f"{side}_id"])
                if p[f"{side}_played"] == 0 and pid in first:
                    self.assertEqual(p[f"{side}_rating"], first[pid])                 # same start in its first week
                first.setdefault(pid, p[f"{side}_rating"])
        self.assertTrue(any(v != 1500 for v in first.values()))

    def test_replay_returns_surface_predictions_by_key(self):
        history = matches(seed=9)
        elo_predictions, surface = r.replay(history, "phase2", keep_surface=lambda m: m["itf_scope"])
        self.assertTrue(all(key[-1] == "itf" for key in surface))
        reference, _ = elo.run_elo(history, elo.SURFACE_ELO_K)
        for p in reference:
            if p["match"]["itf_scope"]:
                self.assertEqual(surface[p["match"]["key"]]["winner_surface_rating"], p["winner_surface_rating"])


if __name__ == "__main__":
    unittest.main()

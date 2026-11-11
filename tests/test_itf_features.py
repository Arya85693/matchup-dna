"""ITF extension features: the history and profile copies reproduce Phases 3-4, and nothing leaks from the match."""
import copy
import unittest

from matchup_dna import elo, features, itf_features as f, profiles
from itf_fixtures import matches

MEANS = {"ATP": {"serve": (0.62, 70.0), "return": (0.38, 70.0), "first_in": (0.6, 70.0), "first_won": (0.7, 42.0),
                 "second_won": (0.5, 28.0), "ace": (0.06, 70.0), "df": (0.04, 70.0), "bp_saved": (0.6, 6.0),
                 "bp_converted": (0.4, 6.0)}}


class CopyTests(unittest.TestCase):
    def test_player_history_with_every_match_counting_is_phase_3s(self):
        history = matches(seed=11)
        predictions, _ = elo.run_elo(history)
        self.assertEqual(f.player_history(history, predictions), features.player_history(history, predictions))

    def test_want_only_drops_values(self):
        history = matches(seed=12)
        predictions, _ = elo.run_elo(history)
        full = features.player_history(history, predictions)
        some = f.player_history(history, predictions, want=lambda m: m["itf_scope"])
        self.assertTrue(some)
        self.assertEqual(some, {k: v for k, v in full.items() if k[0][-1] == "itf"})

    def test_profile_values_are_phase_4s_replay(self):
        history = matches(seed=13)
        ours = f.profile_values(history, profiles.ProfileEngine(MEANS, 52, 4), lambda m: m["itf_scope"])
        theirs, _ = profiles.replay(history, profiles.ProfileEngine(MEANS, 52, 4), keep_from=0)
        self.assertTrue(ours)
        for key, values in ours.items():
            self.assertEqual(values, {field: theirs[key][field] for field in f.PROFILE_KEEP})

    def test_main_only_counts_nothing_from_other_levels(self):
        history = matches(seed=14)
        predictions, _ = elo.run_elo(history)
        counts = f.counts_rule("main_only")
        ours = f.profile_values(history, profiles.ProfileEngine(MEANS, 52, 4), lambda m: m["itf_scope"], counts)
        stripped = [m if m["family"] == "main" else {k: v for k, v in m.items() if k != "stats"} for m in history]
        theirs, _ = profiles.replay(stripped, profiles.ProfileEngine(MEANS, 52, 4), keep_from=0)
        for key, values in ours.items():
            self.assertEqual(values, {field: theirs[key][field] for field in f.PROFILE_KEEP})
        rest = f.player_history(history, predictions, counts, want=lambda m: m["itf_scope"])
        main = [m for m in history if m["family"] == "main"]
        main_predictions, _ = elo.run_elo(main)
        played_main = {}
        for m in sorted(main, key=lambda m: m["tourney_date"]):
            if m["outcome"] in ("completed", "retired"):
                for side in ("winner", "loser"):
                    played_main.setdefault((m["tour"], m[f"{side}_id"]), []).append(m["tourney_date"])
        for (key, side), values in rest.items():
            match = next(m for m in history if m["key"] == key)
            earlier = [d for d in played_main.get((match["tour"], match[f"{side}_id"]), []) if d < match["tourney_date"]]
            self.assertEqual(values["days_since"] is None, not earlier)


class RowTests(unittest.TestCase):
    def rows(self, history, **kw):
        means = {"ATP": MEANS["ATP"]}
        return f.build_rows(history, "phase2", means=means, rows_from=20190101, **kw)

    def test_rows_cover_rated_scored_matches(self):
        history = matches(seed=15)
        rows = self.rows(history)
        expected = [m for m in history if m["itf_scope"] and elo.is_rated(m)]
        self.assertEqual(len(rows), len(expected))
        self.assertTrue(all(r["tier"] == 1 and r["split"] for r in rows))
        self.assertTrue(all("a_serve_adjusted" in r and "b_serve_attempts" in r for r in rows))

    def test_a_matchs_own_result_never_reaches_its_features(self):
        history = matches(seed=16)
        target = [m for m in history if m["itf_scope"] and elo.is_rated(m) and m.get("stats")][-5]
        flipped = copy.deepcopy(history)
        for m in flipped:
            if m["key"] == target["key"]:
                m["winner_id"], m["loser_id"] = m["loser_id"], m["winner_id"]
                m["winner_rank"], m["loser_rank"] = m["loser_rank"], m["winner_rank"]
                m["stats"] = {"w": m["stats"]["l"], "l": m["stats"]["w"]}
        before = {r["match_id"]: r for r in self.rows(history)}
        after = {r["match_id"]: r for r in self.rows(flipped)}
        a, b = before[features.match_id(target)], after[features.match_id(target)]
        self.assertEqual(a["a_id"], b["a_id"])                       # player A depends on the ids, not the winner
        for field in ("a_elo", "b_elo", "a_form", "b_form", "a_days_since", "a_serve_adjusted", "b_return_adjusted"):
            self.assertEqual(a[field], b[field], field)
        self.assertNotEqual(a["a_won"], b["a_won"])


if __name__ == "__main__":
    unittest.main()

import unittest

from matchup_dna.profiles import ProfileEngine, match_observations, replay, serve_counts

MEANS = {"ATP": {stat: (0.6 if stat in ("serve", "first_in", "first_won", "bp_saved") else 0.4, 60.0)
                 for stat in ("serve", "return", "first_in", "first_won", "second_won", "ace", "df", "bp_saved",
                              "bp_converted")}}


def line(svpt=60, first_in=36, first_won=27, second_won=13, ace=5, df=2, bp_saved=3, bp_faced=5):
    return {"ace": ace, "df": df, "svpt": svpt, "1stIn": first_in, "1stWon": first_won, "2ndWon": second_won,
            "SvGms": 9, "bpSaved": bp_saved, "bpFaced": bp_faced}


def played(winner, loser, date, w=None, l=None, number=1, surface="Hard", score="6-4 6-4"):
    from matchup_dna.load import match_outcome
    return {"tour": "ATP", "key": ("ATP", f"T{date}", str(number), "R32"), "tourney_date": date, "surface": surface,
            "winner_id": winner, "loser_id": loser, "outcome": match_outcome(score),
            "stats": {"w": w or line(), "l": l or line(first_won=20, second_won=10)}}


class CountTests(unittest.TestCase):
    def test_serve_counts(self):
        counts = serve_counts(line())
        self.assertEqual(counts["serve"], (40, 60))
        self.assertEqual(counts["first_won"], (27, 36))
        self.assertEqual(counts["second_won"], (13, 24))
        self.assertEqual(counts["bp_saved"], (3, 5))

    def test_no_break_points_faced_adds_nothing(self):
        self.assertNotIn("bp_saved", serve_counts(line(bp_saved=0, bp_faced=0)))

    def test_invalid_lines_add_nothing_they_cannot_support(self):
        counts = serve_counts(line(first_won=40))
        self.assertNotIn("serve", counts)
        self.assertIn("bp_saved", counts)

    def test_return_comes_from_the_opponent_serve(self):
        observed = match_observations(played(1, 2, 20100104))
        self.assertEqual(observed["winner"]["return"], (60 - 30, 60))
        self.assertEqual(observed["loser"]["return"], (60 - 40, 60))
        self.assertEqual(observed["winner"]["bp_converted"], (2, 5))

    def test_only_completed_matches_count(self):
        self.assertEqual(match_observations(played(1, 2, 20100104, score="6-4 2-1 RET")), {})


class PointInTimeAverageTests(unittest.TestCase):
    def test_a_year_uses_only_earlier_years(self):
        from matchup_dna.profiles import prior_year_averages, to_ordinal
        rows = [played(1, 2, 20100104, w=line(first_won=30, second_won=15), l=line(first_won=30, second_won=15)),
                played(1, 2, 20110103, number=2, w=line(first_won=20, second_won=10), l=line(first_won=20, second_won=10)),
                played(1, 2, 20120102, number=3, w=line(first_won=10, second_won=5), l=line(first_won=10, second_won=5))]
        averages = prior_year_averages(rows, min_attempts=0)
        self.assertAlmostEqual(averages("ATP", to_ordinal(20110601))["serve"][0], 45 / 60)
        self.assertAlmostEqual(averages("ATP", to_ordinal(20120601))["serve"][0], (90 + 60) / 240)
        self.assertAlmostEqual(averages("ATP", to_ordinal(20130601))["serve"][0], (90 + 60 + 30) / 360)
        self.assertAlmostEqual(averages("ATP", to_ordinal(20110601))["serve"][1], 60.0)

    def test_the_engine_reads_averages_that_change_with_the_date(self):
        from matchup_dna.profiles import to_ordinal

        def averages(tour, day):
            return {stat: ((0.7 if day >= to_ordinal(20110101) else 0.5), 60.0) for stat in MEANS["ATP"]}
        engine = ProfileEngine(averages, None, 1)
        self.assertAlmostEqual(engine.player("ATP", 9, "Hard", to_ordinal(20100601))["serve"], 0.5)
        self.assertAlmostEqual(engine.player("ATP", 9, "Hard", to_ordinal(20110601))["serve"], 0.7)


class EstimateTests(unittest.TestCase):
    def test_no_history_gives_the_tour_average(self):
        values = ProfileEngine(MEANS, None, 1).player("ATP", 9, "Hard", 100)
        self.assertAlmostEqual(values["serve"], 0.6)
        self.assertEqual(values["serve_attempts"], 0)

    def test_shrinkage_by_hand(self):
        engine = ProfileEngine(MEANS, None, 1)
        features, _ = replay([played(1, 2, 20100104), played(1, 3, 20100111, number=2)], engine, keep_from=20100101)
        later = features[(("ATP", "T20100111", "2", "R32"), "winner")]
        self.assertAlmostEqual(later["serve"], (40 + 1 * 60 * 0.6) / (60 + 60))

    def test_decay_by_hand(self):
        engine = ProfileEngine(MEANS, 1, 1)
        features, _ = replay([played(1, 2, 20100104), played(1, 3, 20100111, number=2)], engine, keep_from=20100101)
        later = features[(("ATP", "T20100111", "2", "R32"), "winner")]
        self.assertAlmostEqual(later["serve"], (0.5 * 40 + 36) / (0.5 * 60 + 60))

    def test_same_week_and_later_matches_are_invisible(self):
        rows = [played(1, 2, 20100104), played(1, 3, 20100104, number=2), played(1, 4, 20100111, number=3)]
        engine = ProfileEngine(MEANS, 52, 2)
        first, _ = replay(rows, engine, keep_from=20100101)
        changed = rows[:2] + [played(1, 4, 20100111, w=line(first_won=10, second_won=5), number=3)]
        second, _ = replay(changed, ProfileEngine(MEANS, 52, 2), keep_from=20100101)
        same_week = (("ATP", "T20100104", "2", "R32"), "winner")
        self.assertEqual(first[same_week]["serve_attempts"], 0)
        for key in first:
            if key[0][1] == "T20100104":
                self.assertEqual(first[key], second[key])

    def test_opponent_adjustment_credits_strong_returners(self):
        engine = ProfileEngine(MEANS, None, 1)
        strong_returner = {"serve": 0.6, "return": 0.5}
        engine.add("ATP", 1, "Hard", 10, {"serve": (36, 60)}, strong_returner)
        values = engine.player("ATP", 1, "Hard", 10)
        self.assertAlmostEqual(values["serve"], (36 + 36) / 120)
        self.assertAlmostEqual(values["serve_adjusted"], (36 + 60 * (0.5 - 0.4) + 36) / 120)

    def test_surface_estimate_is_shrunk_toward_the_player_overall(self):
        engine = ProfileEngine(MEANS, None, 1)
        engine.add("ATP", 1, "Clay", 10, {"serve": (48, 60)}, {"serve": 0.6, "return": 0.4})
        values = engine.player("ATP", 1, "Grass", 10)
        self.assertAlmostEqual(values["serve_surface"], values["serve"])


if __name__ == "__main__":
    unittest.main()

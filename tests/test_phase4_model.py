import math
import random
import unittest

import numpy as np

from matchup_dna.phase4_model import GROUP_COLUMNS, Phase4Logistic, derived_columns, fit_preprocessing
from matchup_dna.round_aware import differences

SIDE_FIELDS = ("rank", "elo_matches", "surface_matches", "days_since", "form", "serve", "return", "serve_adjusted",
               "return_adjusted", "serve_surface", "return_surface", "serve_recent", "return_recent", "first_in",
               "first_won", "second_won", "ace", "df", "bp_saved", "bp_converted", "serve_attempts",
               "recent_games", "ra_elo_shift", "ra_surface_elo_shift", "ra_games_won_share", "ra_games",
               "ra_route_relative_elo", "ra_points", "ra_minutes", "ra_max_opponent_elo", "elo")


def random_row(rng):
    row = {"tour": "ATP", "tourney_date": 20100104 + rng.randrange(0, 90000), "surface": rng.choice(
        ["Hard", "Clay", "Grass"]), "elo_diff": rng.gauss(0, 150), "surface_elo_diff": rng.gauss(0, 150),
        "h2h_a": rng.gauss(0, 0.1), "a_won": rng.random() < 0.5}
    for side in ("a", "b"):
        row[f"{side}_rank"] = rng.choice([None, rng.randrange(1, 300)])
        row[f"{side}_elo_matches"] = rng.randrange(0, 400)
        row[f"{side}_surface_matches"] = rng.randrange(0, 200)
        row[f"{side}_days_since"] = rng.choice([None, rng.randrange(1, 200)])
        row[f"{side}_form"] = rng.gauss(0, 0.1)
        for field in SIDE_FIELDS[5:20]:
            row[f"{side}_{field}"] = rng.uniform(0.05, 0.9)
        row[f"{side}_serve_attempts"] = rng.choice([0, 500.0])
        row[f"{side}_recent_games"] = rng.choice([None, 0, 40])
        row[f"{side}_ra_elo_shift"] = rng.gauss(0, 20)
        row[f"{side}_ra_surface_elo_shift"] = rng.gauss(0, 20)
        row[f"{side}_ra_games_won_share"] = rng.choice([None, rng.uniform(0.3, 0.8)])
        row[f"{side}_ra_games"] = rng.choice([None, 0, 60])
        row[f"{side}_ra_route_relative_elo"] = rng.choice([None, rng.gauss(0, 100)])
        row[f"{side}_ra_points"] = rng.choice([None, 300])
        row[f"{side}_ra_minutes"] = rng.choice([None, 120])
        row[f"{side}_ra_max_opponent_elo"] = rng.choice([None, rng.gauss(1700, 100)])
        row[f"{side}_elo"] = rng.gauss(1700, 100)
    row["rank_diff"] = None
    return row


def swapped(row):
    other = dict(row)
    for field in SIDE_FIELDS:
        other[f"a_{field}"], other[f"b_{field}"] = row[f"b_{field}"], row[f"a_{field}"]
    other["elo_diff"], other["surface_elo_diff"] = -row["elo_diff"], -row["surface_elo_diff"]
    other["h2h_a"] = -row["h2h_a"]
    other["a_won"] = not row["a_won"]
    return other


class SymmetryTests(unittest.TestCase):
    def setUp(self):
        rng = random.Random(0)
        self.rows = [random_row(rng) for _ in range(400)]
        self.preprocessing = fit_preprocessing(self.rows + [swapped(r) for r in self.rows], "adjusted")

    def test_every_column_negates_when_players_swap(self):
        forward = derived_columns(self.rows, self.preprocessing)
        backward = derived_columns([swapped(r) for r in self.rows], self.preprocessing)
        for name, values in forward.items():
            np.testing.assert_allclose(values, -backward[name], atol=1e-9, err_msg=name)

    def test_probabilities_for_both_players_add_to_one(self):
        groups = tuple(g for g in GROUP_COLUMNS if g not in ("elo", "experience", "surface_experience"))
        model = Phase4Logistic(groups, l2=10.0, representation="raw").fit(self.rows)
        p = model.predict(self.rows)
        q = model.predict([swapped(r) for r in self.rows])
        np.testing.assert_allclose(p + q, 1.0, atol=1e-9)

    def test_contributions_add_up_to_the_log_odds(self):
        model = Phase4Logistic(("rank", "serve_return", "product"), l2=10.0).fit(self.rows)
        parts, names = model.contributions(self.rows[:5])
        np.testing.assert_allclose(parts.sum(axis=1), model.log_odds(self.rows[:5]))
        self.assertEqual(len(names), parts.shape[1])


class RoundAwareAgreementTests(unittest.TestCase):
    def test_dataset_columns_match_the_round_aware_definitions(self):
        rng = random.Random(1)
        rows = [random_row(rng) for _ in range(50)]
        for row in rows:
            for side in ("a", "b"):
                row[f"{side}_ra_games"] = rng.choice([0, 25, 60])
        columns = derived_columns(rows, fit_preprocessing(rows, "raw"))
        names = {"ra_elo_shift_logit": "ra_elo_shift_logit", "ra_surface_elo_shift_logit": "ra_surface_elo_shift_logit",
                 "ra_dominance_diff": "ra_dominance_diff", "ra_log_games_diff": "ra_log_games_diff",
                 "ra_route_diff": "ra_route_relative_elo_diff"}
        for index, row in enumerate(rows):
            values = {side: {"elo_shift": row[f"{side}_ra_elo_shift"],
                             "surface_elo_shift": row[f"{side}_ra_surface_elo_shift"],
                             "games_won_share": row[f"{side}_ra_games_won_share"], "games": row[f"{side}_ra_games"],
                             "route_relative_elo": row[f"{side}_ra_route_relative_elo"]} for side in ("a", "b")}
            expected = differences(values["a"], values["b"])
            for column, definition in names.items():
                self.assertAlmostEqual(columns[column][index], expected[definition], msg=column)
        self.assertAlmostEqual(differences({"elo_shift": 0, "surface_elo_shift": 0, "games_won_share": None,
                                            "games": 40, "route_relative_elo": 50.0},
                                           {"elo_shift": 0, "surface_elo_shift": 0, "games_won_share": None,
                                            "games": 25, "route_relative_elo": None})["ra_log_games_diff"],
                               math.log1p(40) - math.log1p(25))


if __name__ == "__main__":
    unittest.main()

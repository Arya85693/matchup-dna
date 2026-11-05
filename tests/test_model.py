import unittest

import numpy as np

from matchup_dna.model import GROUP_ORDER, LogisticModel, design, fit_logistic, fit_preprocessing, sigmoid

PAIRED = ("elo", "elo_matches", "surface_matches", "rank", "days_since", "form", "form_matches")


def synthetic_rows(n, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        a_elo, b_elo = rng.normal(1600, 150, 2)
        a_surface, b_surface = a_elo + rng.normal(0, 60), b_elo + rng.normal(0, 60)
        truth = sigmoid(0.8 * (a_surface - b_surface) * np.log(10) / 400)
        row = {
            "tourney_date": 20100104 + (i % 9) * 10000, "tour": "ATP",
            "a_elo": a_elo, "b_elo": b_elo, "elo_diff": a_elo - b_elo,
            "surface_elo_diff": a_surface - b_surface,
            "a_elo_matches": int(rng.integers(0, 400)), "b_elo_matches": int(rng.integers(0, 400)),
            "a_surface_matches": int(rng.integers(0, 100)), "b_surface_matches": int(rng.integers(0, 100)),
            "a_rank": None if i % 17 == 0 else int(rng.integers(1, 300)), "b_rank": int(rng.integers(1, 300)),
            "a_days_since": None if i % 23 == 0 else int(rng.integers(1, 400)), "b_days_since": int(rng.integers(1, 60)),
            "a_form": float(rng.normal(0, 0.2)), "b_form": float(rng.normal(0, 0.2)),
            "a_form_matches": 10, "b_form_matches": 10,
            "a_won": int(rng.random() < truth),
        }
        rows.append(row)
    return rows


def swapped(row):
    swap = dict(row)
    for field in PAIRED:
        swap[f"a_{field}"], swap[f"b_{field}"] = row[f"b_{field}"], row[f"a_{field}"]
    swap["elo_diff"], swap["surface_elo_diff"] = -row["elo_diff"], -row["surface_elo_diff"]
    swap["a_won"] = 1 - row["a_won"]
    return swap


class NewtonTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.X = rng.normal(size=(2000, 3))
        self.y = (rng.random(2000) < sigmoid(self.X @ np.array([1.0, -0.5, 0.25]))).astype(float)

    def test_matches_scikit_learn(self):
        from sklearn.linear_model import LogisticRegression

        for l2 in (0.0, 10.0):
            ours, _ = fit_logistic(self.X, self.y, l2)
            theirs = LogisticRegression(
                penalty=None if l2 == 0 else "l2", C=1.0 if l2 == 0 else 1 / l2,
                fit_intercept=False, tol=1e-12, max_iter=10_000,
            ).fit(self.X, self.y)
            np.testing.assert_allclose(ours, theirs.coef_[0], atol=1e-5)

    def test_gradient_is_zero_at_the_answer(self):
        w, b = fit_logistic(self.X, self.y, 5.0, intercept=True)
        p = sigmoid(self.X @ w + b)
        np.testing.assert_allclose(self.X.T @ (p - self.y) + 5.0 * w, 0, atol=1e-8)
        self.assertAlmostEqual(float((p - self.y).sum()), 0, places=8)

    def test_penalty_shrinks(self):
        small, _ = fit_logistic(self.X, self.y, 0.0)
        large, _ = fit_logistic(self.X, self.y, 1000.0)
        self.assertLess(np.abs(large).sum(), np.abs(small).sum())


class SymmetryTests(unittest.TestCase):
    def test_swapping_players_negates_every_feature(self):
        rows = synthetic_rows(300)
        preprocessing = fit_preprocessing(rows)
        forward = design(rows, GROUP_ORDER, preprocessing)
        backward = design([swapped(row) for row in rows], GROUP_ORDER, preprocessing)
        np.testing.assert_allclose(forward, -backward, atol=1e-12)

    def test_swapped_probability_is_one_minus(self):
        rows = synthetic_rows(3000)
        model = LogisticModel(GROUP_ORDER, 1.0).fit(rows)
        p = model.predict(rows)
        np.testing.assert_allclose(model.predict([swapped(row) for row in rows]), 1 - p, atol=1e-12)

    def test_elo_only_model_learns_the_shrink(self):
        model = LogisticModel((), 0.0).fit(synthetic_rows(20000, seed=2))
        coefficients = model.unscaled_coefficients()
        self.assertAlmostEqual(coefficients["surface_elo_logit"], 0.8, delta=0.08)
        self.assertAlmostEqual(coefficients["elo_logit"], 0.0, delta=0.08)


class PreprocessingTests(unittest.TestCase):
    def test_learned_values_come_only_from_the_fitting_rows(self):
        rows = synthetic_rows(500)
        before = fit_preprocessing(rows)
        other = synthetic_rows(500, seed=9)
        for row in other:
            row["a_rank"] = row["b_rank"] = 5000
        model = LogisticModel(GROUP_ORDER, 1.0).fit(rows)
        model.predict(other)
        self.assertEqual(model.preprocessing, before)
        self.assertLess(before["rank_impute"], 300)


if __name__ == "__main__":
    unittest.main()

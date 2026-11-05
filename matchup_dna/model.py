"""Logistic regression written out by hand, and the Phase 3 feature groups.

Player A is assigned at random, so every model here must give P(B beats A) = 1 - P(A beats B). Each feature
is an A-minus-B difference, or a difference times something symmetric, so swapping the players negates
every feature. With no intercept, the fitted probability then flips exactly.
"""
import math

import numpy as np

LN10_OVER_400 = math.log(10) / 400
INACTIVITY_CAP = 365
RANK_IMPUTE_QUANTILE = 0.99

# Fixed order for adding groups in Experiment C. "elo" is Experiment B and is always included.
GROUP_ORDER = ("rank", "experience", "surface_experience", "inactivity", "form")
GROUP_COLUMNS = {
    "elo": ("elo_logit", "surface_elo_logit"),
    "rank": ("log_rank_diff", "rank_missing_diff"),
    "experience": ("log_matches_diff", "surface_logit_x_experience"),
    "surface_experience": ("log_surface_matches_diff",),
    "inactivity": ("log_days_since_diff",),
    "form": ("form_diff",),
}
L2_GRID = (0.0, 1.0, 10.0, 100.0, 1000.0, 3000.0, 10000.0, 30000.0)


def sigmoid(z):
    return 0.5 * (1 + np.tanh(0.5 * z))


def logit(p):
    p = np.asarray(p, dtype=float)
    return np.log(p) - np.log1p(-p)


def fit_logistic(X, y, l2=0.0, intercept=False, iterations=100, tolerance=1e-10):
    """Minimizes  -sum[y log p + (1 - y) log(1 - p)] + (l2 / 2) * |w|^2  by Newton's method.

    Each step solves (X' S X + l2 I) step = X' (p - y) + l2 w, where S holds p(1 - p) on its diagonal.
    The intercept, if any, is not penalized. Returns (coefficients, intercept).
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if intercept:
        X = np.column_stack([np.ones(len(X)), X])
    penalty = np.full(X.shape[1], float(l2))
    if intercept:
        penalty[0] = 0.0
    w = np.zeros(X.shape[1])
    for _ in range(iterations):
        p = sigmoid(X @ w)
        gradient = X.T @ (p - y) + penalty * w
        hessian = (X * (p * (1 - p))[:, None]).T @ X + np.diag(penalty)
        step = np.linalg.solve(hessian, gradient)
        w -= step
        if np.max(np.abs(step)) < tolerance:
            break
    else:
        raise RuntimeError("Newton's method did not converge")
    if intercept:
        return w[1:], w[0]
    return w, 0.0


def column(rows, field, default=None):
    return np.array([default if row[field] is None else row[field] for row in rows], dtype=float)


def fit_preprocessing(rows):
    """Values learned from the fitting rows only: the rank given to unranked players and the mean log experience."""
    ranks = np.array([row[side] for row in rows for side in ("a_rank", "b_rank") if row[side] is not None])
    experience = np.log1p(np.minimum(column(rows, "a_elo_matches"), column(rows, "b_elo_matches")))
    return {
        "rank_impute": float(np.quantile(ranks, RANK_IMPUTE_QUANTILE)),
        "experience_mean": float(experience.mean()),
    }


def derived_columns(rows, preprocessing):
    """Every candidate feature, as a dict of arrays. Each one changes sign when A and B swap."""
    impute = preprocessing["rank_impute"]
    elo_logit = column(rows, "elo_diff") * LN10_OVER_400
    surface_logit = column(rows, "surface_elo_diff") * LN10_OVER_400
    a_matches, b_matches = column(rows, "a_elo_matches"), column(rows, "b_elo_matches")
    a_days = np.minimum(column(rows, "a_days_since", INACTIVITY_CAP), INACTIVITY_CAP)
    b_days = np.minimum(column(rows, "b_days_since", INACTIVITY_CAP), INACTIVITY_CAP)
    return {
        "elo_logit": elo_logit,
        "surface_elo_logit": surface_logit,
        "log_rank_diff": np.log(column(rows, "a_rank", impute)) - np.log(column(rows, "b_rank", impute)),
        "rank_missing_diff": (
            np.array([row["a_rank"] is None for row in rows], dtype=float)
            - np.array([row["b_rank"] is None for row in rows], dtype=float)
        ),
        "log_matches_diff": np.log1p(a_matches) - np.log1p(b_matches),
        "surface_logit_x_experience": surface_logit
        * (np.log1p(np.minimum(a_matches, b_matches)) - preprocessing["experience_mean"]),
        "log_surface_matches_diff": (
            np.log1p(column(rows, "a_surface_matches", 0)) - np.log1p(column(rows, "b_surface_matches", 0))
        ),
        "log_days_since_diff": np.log1p(a_days) - np.log1p(b_days),
        "form_diff": column(rows, "a_form") - column(rows, "b_form"),
    }


def feature_names(groups):
    return [name for group in ("elo",) + tuple(groups) for name in GROUP_COLUMNS[group]]


def design(rows, groups, preprocessing):
    derived = derived_columns(rows, preprocessing)
    return np.column_stack([derived[name] for name in feature_names(groups)])


def labels(rows):
    return np.array([row["a_won"] for row in rows], dtype=float)


class LogisticModel:
    """No-intercept logistic regression on the "elo" group plus `groups`, with features divided by their
    root-mean-square on the fitting rows. Dividing (not centering) keeps every feature antisymmetric."""

    def __init__(self, groups=(), l2=0.0):
        self.groups = tuple(groups)
        self.l2 = l2

    def fit(self, rows):
        self.preprocessing = fit_preprocessing(rows)
        X = design(rows, self.groups, self.preprocessing)
        self.scale = np.sqrt((X ** 2).mean(axis=0))
        self.scale[self.scale == 0] = 1.0
        self.coefficients, _ = fit_logistic(X / self.scale, labels(rows), self.l2)
        return self

    def predict(self, rows):
        return sigmoid(design(rows, self.groups, self.preprocessing) / self.scale @ self.coefficients)

    def unscaled_coefficients(self):
        return dict(zip(feature_names(self.groups), self.coefficients / self.scale))


def mean_log_loss(p, y):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def choose_l2(rows, groups, inner_start=20180101, grid=L2_GRID):
    """L2 chosen inside the fitting rows: fit on weeks before inner_start, score on the rest, keep the best."""
    early = [row for row in rows if row["tourney_date"] < inner_start]
    late = [row for row in rows if row["tourney_date"] >= inner_start]
    scores = {l2: mean_log_loss(LogisticModel(groups, l2).fit(early).predict(late), labels(late)) for l2 in grid}
    return min(scores, key=scores.get), scores

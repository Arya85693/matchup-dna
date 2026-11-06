"""Phase 4 features and the logistic model that uses them.

Every feature is antisymmetric: swapping player A and player B negates it. A feature is an A-minus-B difference,
a difference times something symmetric (the same for A and B), or a contrast such as x_A * y_B - x_B * y_A.
With no intercept, the model then gives P(B beats A) = 1 - P(A beats B) exactly, as Phase 3 requires.

Groups (each column is A minus B unless stated):

    Phase 3 groups        elo, rank, inactivity, form (matchup_dna.model)
    serve_return          logit(serve) and logit(return) estimates; "no statistics history" indicator
    surface_serve_return  logit of the surface-specific serve and return estimates
    recent_serve_return   logit of the short-half-life serve and return estimates
    serve_components      logit of first serves in, first-serve points won, second-serve points won, aces, and
                          double faults per service point
    break_points          logit of break points saved and converted
    product               a_A * b_B - a_B * b_A, where a = serve - mu_serve and b = return - mu_return
                          (does A's serve edge matter more against a strong or a weak returner?)
    dominance_elo         Elo log-odds * (serve dominance - its mean), where serve dominance is
                          (a_A + a_B - b_A - b_B) / 2, how serve-dominated the matchup is expected to be
    surface_interactions  serve and return differences times grass and times clay indicators
    head_to_head          A's earlier results against B minus Elo's expectation, shrunk (already antisymmetric)
    recent_workload       log(1 + games in the previous 14 days); missing indicator
    ra_controls           round-aware Elo and surface-Elo shifts (log-odds); earlier-round share of games won - 0.5
    ra_workload           log(1 + games in earlier rounds); missing indicator
    ra_route              mean (opponent start-of-week Elo - own) in log-odds units, 0 with no opponent played
    ra_workload_route     g_A * r_A - g_B * r_B, with g the log games and r the route value

Serve and return use the raw or opponent-adjusted estimates per tour, as chosen by the `profiles` command.
"""
import math

import numpy as np

from matchup_dna.model import GROUP_COLUMNS as PHASE3_COLUMNS, L2_GRID, derived_columns as phase3_columns
from matchup_dna.model import fit_logistic, fit_preprocessing as phase3_preprocessing, labels, mean_log_loss, sigmoid

PHASE3_GROUPS = ("rank", "inactivity", "form")
LN10_OVER_400 = math.log(10) / 400
COMPONENTS = ("first_in", "first_won", "second_won", "ace", "df")
GROUP_COLUMNS = dict(PHASE3_COLUMNS)
GROUP_COLUMNS.update({
    "serve_return": ("serve_diff", "return_diff", "no_stats_diff"),
    "surface_serve_return": ("serve_surface_diff", "return_surface_diff"),
    "recent_serve_return": ("serve_recent_diff", "return_recent_diff"),
    "serve_components": tuple(f"{stat}_diff" for stat in COMPONENTS),
    "break_points": ("bp_saved_diff", "bp_converted_diff"),
    "product": ("serve_return_product",),
    "dominance_elo": ("elo_x_serve_dominance",),
    "surface_interactions": ("serve_diff_x_grass", "return_diff_x_grass", "serve_diff_x_clay", "return_diff_x_clay"),
    "head_to_head": ("h2h",),
    "recent_workload": ("log_recent_games_diff", "recent_games_missing_diff"),
    "ra_controls": ("ra_elo_shift_logit", "ra_surface_elo_shift_logit", "ra_dominance_diff"),
    "ra_workload": ("ra_log_games_diff", "ra_games_missing_diff"),
    "ra_route": ("ra_route_diff",),
    "ra_workload_route": ("ra_workload_route",),
    # Diagnostics only (reported, never selected): the workload measure as points or minutes, and the
    # strongest opponent beaten.
    "ra_points_diagnostic": ("ra_log_points_diff", "ra_points_missing_diff"),
    "ra_minutes_diagnostic": ("ra_log_minutes_diff", "ra_minutes_missing_diff"),
    "ra_max_opponent_diagnostic": ("ra_max_opponent_diff",),
})


def _column(rows, field, default=0.0):
    return np.array([default if row.get(field) is None else row[field] for row in rows], dtype=float)


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p) - np.log1p(-p)


def _missing(rows, field):
    return np.array([row.get(field) is None for row in rows], dtype=float)


def serve_fields(representation):
    return ("serve_adjusted", "return_adjusted") if representation == "adjusted" else ("serve", "return")


def fit_preprocessing(rows, representation):
    """Phase 3's learned values plus the serve and return centers and the mean serve dominance, from these rows."""
    found = phase3_preprocessing(rows)
    serve, ret = serve_fields(representation)
    serve_mean = float(np.mean(np.concatenate([_column(rows, f"a_{serve}"), _column(rows, f"b_{serve}")])))
    return_mean = float(np.mean(np.concatenate([_column(rows, f"a_{ret}"), _column(rows, f"b_{ret}")])))
    found.update(representation=representation, serve_mean=serve_mean, return_mean=return_mean)
    found["dominance_mean"] = float(np.mean(_dominance(rows, found)))
    return found


def _centered(rows, preprocessing):
    serve, ret = serve_fields(preprocessing["representation"])
    a = {s: _column(rows, f"{s}_{serve}") - preprocessing["serve_mean"] for s in ("a", "b")}
    b = {s: _column(rows, f"{s}_{ret}") - preprocessing["return_mean"] for s in ("a", "b")}
    return a, b


def _dominance(rows, preprocessing):
    a, b = _centered(rows, preprocessing)
    return (a["a"] + a["b"] - b["a"] - b["b"]) / 2


def _log_count(rows, field):
    return np.log1p(_column(rows, field))


def derived_columns(rows, preprocessing):
    """Every candidate column, as a dict of arrays. Each one changes sign when A and B swap."""
    found = phase3_columns(rows, preprocessing)
    serve, ret = serve_fields(preprocessing["representation"])
    found["serve_diff"] = _logit(_column(rows, f"a_{serve}")) - _logit(_column(rows, f"b_{serve}"))
    found["return_diff"] = _logit(_column(rows, f"a_{ret}")) - _logit(_column(rows, f"b_{ret}"))
    found["no_stats_diff"] = (np.array([not row["a_serve_attempts"] for row in rows], dtype=float)
                              - np.array([not row["b_serve_attempts"] for row in rows], dtype=float))
    for name, field in (("serve_surface", "serve_surface"), ("return_surface", "return_surface"),
                        ("serve_recent", "serve_recent"), ("return_recent", "return_recent"),
                        ("bp_saved", "bp_saved"), ("bp_converted", "bp_converted")) + tuple((s, s) for s in COMPONENTS):
        found[f"{name}_diff"] = _logit(_column(rows, f"a_{field}")) - _logit(_column(rows, f"b_{field}"))
    a, b = _centered(rows, preprocessing)
    found["serve_return_product"] = a["a"] * b["b"] - a["b"] * b["a"]
    found["elo_x_serve_dominance"] = found["elo_logit"] * (_dominance(rows, preprocessing) - preprocessing["dominance_mean"])
    grass = np.array([row["surface"] == "Grass" for row in rows], dtype=float)
    clay = np.array([row["surface"] == "Clay" for row in rows], dtype=float)
    for indicator, label in ((grass, "grass"), (clay, "clay")):
        found[f"serve_diff_x_{label}"] = found["serve_diff"] * indicator
        found[f"return_diff_x_{label}"] = found["return_diff"] * indicator
    found["h2h"] = _column(rows, "h2h_a")
    found["log_recent_games_diff"] = _log_count(rows, "a_recent_games") - _log_count(rows, "b_recent_games")
    found["recent_games_missing_diff"] = _missing(rows, "a_recent_games") - _missing(rows, "b_recent_games")

    found["ra_elo_shift_logit"] = (_column(rows, "a_ra_elo_shift") - _column(rows, "b_ra_elo_shift")) * LN10_OVER_400
    found["ra_surface_elo_shift_logit"] = (_column(rows, "a_ra_surface_elo_shift")
                                           - _column(rows, "b_ra_surface_elo_shift")) * LN10_OVER_400
    share_a = _column(rows, "a_ra_games_won_share", 0.5) - 0.5
    share_b = _column(rows, "b_ra_games_won_share", 0.5) - 0.5
    found["ra_dominance_diff"] = share_a - share_b
    games_a, games_b = _log_count(rows, "a_ra_games"), _log_count(rows, "b_ra_games")
    found["ra_log_games_diff"] = games_a - games_b
    found["ra_games_missing_diff"] = _missing(rows, "a_ra_games") - _missing(rows, "b_ra_games")
    route_a = _column(rows, "a_ra_route_relative_elo") * LN10_OVER_400
    route_b = _column(rows, "b_ra_route_relative_elo") * LN10_OVER_400
    found["ra_route_diff"] = route_a - route_b
    found["ra_workload_route"] = games_a * route_a - games_b * route_b
    for measure in ("points", "minutes"):
        found[f"ra_log_{measure}_diff"] = _log_count(rows, f"a_ra_{measure}") - _log_count(rows, f"b_ra_{measure}")
        found[f"ra_{measure}_missing_diff"] = _missing(rows, f"a_ra_{measure}") - _missing(rows, f"b_ra_{measure}")
    own_a = _column(rows, "a_elo", 1500.0)
    own_b = _column(rows, "b_elo", 1500.0)
    top_a = np.where(_missing(rows, "a_ra_max_opponent_elo") == 1, own_a, _column(rows, "a_ra_max_opponent_elo"))
    top_b = np.where(_missing(rows, "b_ra_max_opponent_elo") == 1, own_b, _column(rows, "b_ra_max_opponent_elo"))
    found["ra_max_opponent_diff"] = ((top_a - own_a) - (top_b - own_b)) * LN10_OVER_400
    return found


def feature_names(groups):
    return [name for group in ("elo",) + tuple(groups) for name in GROUP_COLUMNS[group]]


def design(rows, groups, preprocessing):
    derived = derived_columns(rows, preprocessing)
    return np.column_stack([derived[name] for name in feature_names(groups)])


class Phase4Logistic:
    """No-intercept logistic regression on Elo plus `groups`, features divided by their root-mean-square on the
    fitting rows (dividing, not centering, keeps them antisymmetric). L2 penalty as in Phase 3."""

    def __init__(self, groups=(), l2=0.0, representation="raw"):
        self.groups, self.l2, self.representation = tuple(groups), l2, representation

    def fit(self, rows):
        self.preprocessing = fit_preprocessing(rows, self.representation)
        X = design(rows, self.groups, self.preprocessing)
        self.scale = np.sqrt((X ** 2).mean(axis=0))
        active = self.scale > 0
        self.scale[~active] = 1.0
        # A column that is zero on every fitting row carries no information: its coefficient is 0, and the others
        # are fitted as usual (with no penalty such a column would make Newton's method singular).
        self.coefficients = np.zeros(X.shape[1])
        self.coefficients[active], _ = fit_logistic(X[:, active] / self.scale[active], labels(rows), self.l2)
        return self

    def log_odds(self, rows):
        return design(rows, self.groups, self.preprocessing) / self.scale @ self.coefficients

    def predict(self, rows):
        return sigmoid(self.log_odds(rows))

    def contributions(self, rows):
        """Per row and feature, coefficient times feature value on the log-odds scale. They add up to the log-odds."""
        X = design(rows, self.groups, self.preprocessing) / self.scale
        return X * self.coefficients, feature_names(self.groups)

    def unscaled_coefficients(self):
        return dict(zip(feature_names(self.groups), self.coefficients / self.scale))


def choose_l2(rows, groups, representation, inner_start=20180101, grid=L2_GRID):
    """L2 chosen inside the fitting rows: fit on weeks before inner_start, score on the rest (as Phase 3)."""
    early = [row for row in rows if row["tourney_date"] < inner_start]
    late = [row for row in rows if row["tourney_date"] >= inner_start]
    scores = {}
    for l2 in grid:
        try:
            scores[l2] = mean_log_loss(Phase4Logistic(groups, l2, representation).fit(early).predict(late), labels(late))
        except (np.linalg.LinAlgError, RuntimeError):
            # With no penalty, a rare indicator whose few rows all have one outcome has no finite estimate
            # (separation), so Newton's method fails. That L2 cannot be chosen; any L2 above zero always has one.
            scores[l2] = float("inf")
    return min(scores, key=scores.get), scores

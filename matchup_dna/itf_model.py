"""ITF extension, stage I3: the models compared on ITF matches, and how they are scored.

    B0  rank only: logistic on log rank ratio and unranked flags
    B1  all-level Elo on its own: the ordinary Elo probability, nothing fitted
    B2  the frozen production main-tour model (models/phase4_tournament_start.json) applied unchanged, to rows built
        from main-tour history only, as the live main-tour system would see these players
    M1  Elo (ordinary and surface), rank, rest, form, and Elo times the field-strength tier
    M2  M1 plus the opponent-adjusted serve and return profiles and a "no statistics history" flag

Every fitted model is Phase 3's no-intercept logistic regression with features divided by their root-mean-square
(matchup_dna.model.fit_logistic, unchanged), fitted per tour. Columns come from phase4_model.derived_columns
(unchanged) plus one new antisymmetric column, elo_x_tier = Elo log-odds * (tier - its mean on the fitting rows):
does rating matter more at stronger events? Swapping the players negates every column, so P(B wins) = 1 - P(A wins).

L2 is chosen per tour inside development (fit before 1 July 2024, score the year after) on M1's columns, and M2 uses
the same value: before 2025 the serve columns are all zero, so an inner split cannot judge them.
"""
import numpy as np

from matchup_dna.elo import expected_score
from matchup_dna.model import L2_GRID, fit_logistic, labels, mean_log_loss, sigmoid
from matchup_dna.phase4_model import derived_columns as phase4_columns, fit_preprocessing as phase4_preprocessing

REPRESENTATION = "adjusted"
COLUMNS = {
    "B0": ("log_rank_diff", "rank_missing_diff"),
    "M1": ("elo_logit", "surface_elo_logit", "log_rank_diff", "rank_missing_diff", "log_days_since_diff", "form_diff",
           "elo_x_tier"),
}
COLUMNS["M2"] = COLUMNS["M1"] + ("serve_diff", "return_diff", "no_stats_diff")
FITTED = ("B0", "M1", "M2")
INNER_START = 20240701
BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 20261110
CALIBRATION_BINS = 10


def preprocessing(rows):
    found = phase4_preprocessing(rows, REPRESENTATION)
    found["tier_mean"] = float(np.mean([row["tier"] for row in rows]))
    return found


def columns(rows, prep):
    found = phase4_columns(rows, prep)
    tiers = np.array([row["tier"] for row in rows], dtype=float)
    found["elo_x_tier"] = found["elo_logit"] * (tiers - prep["tier_mean"])
    return found


def design(rows, names, prep):
    found = columns(rows, prep)
    return np.column_stack([found[name] for name in names])


class ITFLogistic:
    def __init__(self, name, l2=0.0):
        self.name, self.names, self.l2 = name, COLUMNS[name], l2

    def fit(self, rows):
        self.prep = preprocessing(rows)
        X = design(rows, self.names, self.prep)
        self.scale = np.sqrt((X ** 2).mean(axis=0))
        active = self.scale > 0
        self.scale[~active] = 1.0
        self.coefficients = np.zeros(X.shape[1])
        self.coefficients[active], _ = fit_logistic(X[:, active] / self.scale[active], labels(rows), self.l2)
        return self

    def predict(self, rows):
        return sigmoid(design(rows, self.names, self.prep) / self.scale @ self.coefficients)

    def spec(self):
        return {"model": self.name, "columns": list(self.names), "l2": self.l2, "preprocessing": self.prep,
                "scale": self.scale.tolist(), "coefficients": self.coefficients.tolist(),
                "coefficients_per_unit": dict(zip(self.names, (self.coefficients / self.scale).tolist()))}


def elo_probability(rows):
    return np.array([expected_score(row["a_elo"], row["b_elo"]) for row in rows])


def choose_l2(rows, name="M1", inner_start=INNER_START, grid=L2_GRID):
    early = [row for row in rows if row["tourney_date"] < inner_start]
    late = [row for row in rows if row["tourney_date"] >= inner_start]
    scores = {}
    for l2 in grid:
        try:
            scores[l2] = mean_log_loss(ITFLogistic(name, l2).fit(early).predict(late), labels(late))
        except (np.linalg.LinAlgError, RuntimeError):
            scores[l2] = float("inf")
    return min(scores, key=scores.get), scores


def metrics(p, y):
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    return {"matches": int(len(y)), "log_loss": mean_log_loss(p, y), "brier": float(np.mean((p - y) ** 2)),
            "accuracy": float(np.mean((p > 0.5) == (y == 1))), "calibration": calibration(p, y)}


def calibration(p, y, bins=CALIBRATION_BINS):
    """Equal-width bins of the probability for player A; with A assigned at random, bins are symmetric around 0.5.
    Returns the rows per bin and the expected calibration error (mean |forecast - outcome| weighted by bin size)."""
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    table, error = [], 0.0
    for b in range(bins):
        inside = index == b
        if inside.any():
            forecast, observed = float(p[inside].mean()), float(y[inside].mean())
            table.append({"bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}", "matches": int(inside.sum()),
                          "forecast": forecast, "observed": observed})
            error += inside.sum() * abs(forecast - observed)
    return {"bins": table, "ece": float(error / len(p))}


def row_losses(p, y):
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, dtype=float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def paired_bootstrap(loss_a, loss_b, clusters, reps=BOOTSTRAP_REPS, seed=BOOTSTRAP_SEED):
    """Mean of (loss_a - loss_b) per match, and its bootstrap standard error and 95% interval, resampling whole
    editions (matches in one event share players and conditions, so they are not independent)."""
    diff = np.asarray(loss_a) - np.asarray(loss_b)
    groups = {}
    for i, c in enumerate(clusters):
        groups.setdefault(c, []).append(i)
    sums = np.array([diff[idx].sum() for idx in groups.values()])
    sizes = np.array([len(idx) for idx in groups.values()])
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(sums), size=(reps, len(sums)))
    means = sums[draws].sum(axis=1) / sizes[draws].sum(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return {"mean": float(diff.mean()), "se": float(means.std(ddof=1)), "ci95": [float(low), float(high)],
            "editions": int(len(sums)), "reps": reps, "seed": seed}

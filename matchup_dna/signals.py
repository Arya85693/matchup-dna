"""Model-against-market signals for Phase 5.

The brief separates five things, and so does this module:
1. a prediction: the model's probability that player A wins;
2. a measured discrepancy: model probability minus the market's margin-free probability;
3. a hypothesis that the discrepancy carries information: tested here as a regression slope and as a blend;
4. a simulated decision (backtest.py);
5. an economic outcome, which needs real execution evidence that this project does not have.

Every function is symmetric in the two players: swapping A and B negates a discrepancy and leaves every test the
same.
"""
import math

import numpy as np

from matchup_dna import market
from matchup_dna.model import fit_logistic, sigmoid


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def market_probability(odds_a, odds_b, method):
    """Player A's margin-free probability from the two decimal prices."""
    return market.fair((odds_a, odds_b), method)[0]


def discrepancy(p_model, p_market):
    return np.asarray(p_model, dtype=float) - np.asarray(p_market, dtype=float)


def information_slope(p_model, p_market, y, clusters):
    """Does the discrepancy predict what the market misses? The slope b of y - p_market = b (p_model - p_market),
    fitted through the origin (both sides are symmetric), with a standard error clustered by tournament date.
    b = 0: the model's disagreements carry no information beyond the price. b = 1: the model is right where it
    disagrees. Between: the model knows something, but less than its disagreement suggests."""
    d = discrepancy(p_model, p_market)
    residual = np.asarray(y, dtype=float) - np.asarray(p_market, dtype=float)
    sxx = float((d * d).sum())
    if sxx == 0:
        return float("nan"), float("nan")
    b = float((d * residual).sum() / sxx)
    error = residual - b * d
    totals = {}
    for cluster, value in zip(clusters, d * error):
        totals[cluster] = totals.get(cluster, 0.0) + value
    g = len(totals)
    se = math.sqrt(g / (g - 1) * sum(v * v for v in totals.values())) / sxx if g > 1 else float("nan")
    return b, se


def fit_blend(p_market, p_model, y):
    """Weights (market, model) of logit P(A wins) = w_m logit(p_market) + w_x logit(p_model), no intercept (so the
    two players' probabilities sum to 1). A model weight near zero means the model adds nothing to the price."""
    X = np.column_stack([logit(p_market), logit(p_model)])
    coefficients, _ = fit_logistic(X, np.asarray(y, dtype=float), l2=0.0, intercept=False)
    return float(coefficients[0]), float(coefficients[1])


def blend(weights, p_market, p_model):
    return sigmoid(weights[0] * logit(p_market) + weights[1] * logit(p_model))


def bucket_table(p_model, p_market, y, edges=(-1.0, -0.15, -0.10, -0.05, -0.02, 0.02, 0.05, 0.10, 0.15, 1.0)):
    """Discrepancy buckets: matches, mean discrepancy, mean market probability, observed win share. Shown from player
    A's side; because A is chosen at random, a bucket and its mirror image describe the same kind of match."""
    d = discrepancy(p_model, p_market)
    y = np.asarray(y, dtype=float)
    p_market = np.asarray(p_market, dtype=float)
    rows = []
    for low, high in zip(edges, edges[1:]):
        mask = (d >= low) & (d < high)
        if mask.any():
            rows.append({"low": low, "high": high, "matches": int(mask.sum()), "mean_discrepancy": float(d[mask].mean()),
                         "market": float(p_market[mask].mean()), "model": float(np.asarray(p_model)[mask].mean()),
                         "observed": float(y[mask].mean())})
    return rows

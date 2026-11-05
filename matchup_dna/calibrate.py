"""Recalibrating an existing probability without adding information.

Temperature scaling keeps the log-odds' sign and multiplies their size: p' = sigmoid(b * logit(p)).
b < 1 pulls every probability toward 0.5, which is the fix for an overconfident model. Platt scaling adds an
intercept, sigmoid(a + b * logit(p)). Player A is random, so a should come out near 0, and the Phase 3
models use temperature scaling, which keeps P(A) + P(B) = 1.
"""
import numpy as np

from matchup_dna.model import fit_logistic, logit, sigmoid


def fit_temperature(p, y):
    coefficients, _ = fit_logistic(logit(p)[:, None], y)
    return float(coefficients[0])


def apply_temperature(p, b):
    return sigmoid(b * logit(p))


def fit_platt(p, y):
    coefficients, intercept = fit_logistic(logit(p)[:, None], y, intercept=True)
    return float(intercept), float(coefficients[0])


def apply_platt(p, a, b):
    return sigmoid(a + b * logit(p))

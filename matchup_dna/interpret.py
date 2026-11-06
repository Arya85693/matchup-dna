"""Explaining a logistic prediction feature by feature.

The model is logit P(A wins) = sum over features of coefficient * scaled feature, with no intercept. So each
feature's term is an exact share of the log-odds: the terms add up to the prediction. Near a probability p, a
term c moves the probability by about p (1 - p) c. These are associations learned from past matches, not causes.
"""
import math

# Strongly correlated inputs are shown as one line: ordinary and surface Elo carry largely the same signal, so
# the model's split between them (one coefficient can even turn negative) is not interpretable on its own.
LABELS = {
    "elo_logit": "Elo ratings (overall and surface together)", "surface_elo_logit": "Elo ratings (overall and surface together)",
    "log_rank_diff": "Ranking (gap and missing rank)", "rank_missing_diff": "Ranking (gap and missing rank)",
    "log_days_since_diff": "Days since last match", "form_diff": "Recent results against Elo",
    "serve_diff": "Serving strength", "return_diff": "Returning strength", "no_stats_diff": "No statistics history",
    "log_matches_diff": "Experience",
}


def explain(model, row):
    """[(label, term in log-odds)] with correlated inputs combined, sorted by size, and the total log-odds."""
    parts, names = model.contributions([row])
    combined = {}
    for name, value in zip(names, parts[0]):
        label = LABELS.get(name, name)
        combined[label] = combined.get(label, 0.0) + float(value)
    terms = sorted(combined.items(), key=lambda item: -abs(item[1]))
    return terms, float(parts[0].sum())


def probability_effect(term, p):
    """Approximate change in win probability from one log-odds term near probability p."""
    return p * (1 - p) * term


def describe(terms, p, a_name, b_name, top=6):
    lines = []
    for label, term in terms[:top]:
        if abs(term) < 1e-4:
            continue
        favored = a_name if term > 0 else b_name
        lines.append(f"{label:<44} {term:+.3f} log-odds, about {abs(probability_effect(term, p)) * 100:.1f} points "
                     f"toward {favored}")
    return lines


def logit(p):
    return math.log(p) - math.log(1 - p)

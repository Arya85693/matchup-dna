"""Pre-registered forward selection for Phase 4, using Phase 3's keep rule unchanged.

Every comparison is fair in the same way: the baseline and the candidate are fitted on the same rows, per tour,
and each gets its own L2 from the same inner split (fit 2010-2017, score 2018-2020) and the same grid. For every
gain that is kept, two sensitivity checks rerun the comparison with the L2 values swapped:

    candidate at the baseline's L2   minus   baseline            (is the gain from the features?)
    candidate                        minus   baseline at the candidate's L2   (or from a different penalty?)

A gain that disappears in either check is reported as a regularization artifact.
"""
import numpy as np

from matchup_dna.experiment import describe_keep, keep_rule, per_tour, tour_rows
from matchup_dna.load import TOURS
from matchup_dna.model import fit_logistic, labels, logit
from matchup_dna.phase4_model import Phase4Logistic, choose_l2


def chosen_l2(train, groups, representations):
    return {tour: choose_l2(tour_rows(train, tour), groups, representations[tour])[0] for tour in TOURS}


def logistic(groups, l2, representations):
    def fit_predict(fit_rows, target_rows):
        tour = fit_rows[0]["tour"]
        return Phase4Logistic(groups, l2[tour], representations[tour]).fit(fit_rows).predict(target_rows)
    return fit_predict


def fit_models(train, groups, l2, representations):
    return {tour: Phase4Logistic(groups, l2[tour], representations[tour]).fit(tour_rows(train, tour)) for tour in TOURS}


def model_state(train, validation, groups, representations, l2=None):
    l2 = l2 or chosen_l2(train, groups, representations)
    return {"groups": tuple(groups), "l2": l2, "p": per_tour(train, validation, logistic(groups, l2, representations))}


def cross_l2(train, validation, y, current, candidate, representations):
    """Combined gaps of the two sensitivity checks (see the module notes): ((gap, se), (gap, se))."""
    at_base = per_tour(train, validation, logistic(candidate["groups"], current["l2"], representations))
    base_at_candidate = per_tour(train, validation, logistic(current["groups"], candidate["l2"], representations))
    first = keep_rule(validation, y, at_base, current["p"])["gaps"]["Both"]
    second = keep_rule(validation, y, candidate["p"], base_at_candidate)["gaps"]["Both"]
    return first, second


def forward(train, validation, y, base, order, representations, out, title):
    """Adds each group in `order` to the current model and keeps it if the keep rule passes. Returns
    (final state, trail of (group, outcome, sensitivity))."""
    current = base
    out(f"\n{title}")
    trail = []
    for group in order:
        candidate = model_state(train, validation, current["groups"] + (group,), representations)
        outcome = keep_rule(validation, y, candidate["p"], current["p"])
        describe_keep(out, f"+ {group} (L2 {candidate['l2']})", outcome)
        sensitivity = None
        if outcome["passed"]:
            sensitivity = cross_l2(train, validation, y, current, candidate, representations)
            out(f"      sensitivity: candidate at baseline L2 {sensitivity[0][0]:+.4f} (se {sensitivity[0][1]:.4f}); "
                f"against baseline at candidate L2 {sensitivity[1][0]:+.4f} (se {sensitivity[1][1]:.4f})")
            current = candidate
        trail.append((group, outcome, sensitivity))
    return current, trail


def calibration_line(p, y):
    """(intercept, slope) of logit P(y) = intercept + slope * logit(p), fitted on these rows. A well-calibrated
    model has intercept near 0 and slope near 1; a slope below 1 means overconfident."""
    x = logit(np.clip(p, 1e-9, 1 - 1e-9))[:, None]
    coefficients, intercept = fit_logistic(x, y, l2=0.0, intercept=True)
    return float(intercept), float(coefficients[0])


def count_comparisons(trail):
    return len(trail)

"""Uncertainty for Phase 5: means with standard errors clustered by tournament date, and a bootstrap that resamples
whole tournament dates.

Matches on one tourney_date share players, conditions and the bookmaker's view of them, so they are not
independent. As in Phases 3 and 4, a tourney_date is one cluster. Clustered standard errors suit averages (log-loss
gaps, return per unit staked). The cluster bootstrap suits statistics without a simple formula: the maximum
drawdown of a backtest, or a return whose stakes depend on earlier results.
"""
import math
import random
from collections import defaultdict

from matchup_dna.evaluate import clustered_standard_error

SEED = 20261108
DRAWS = 2000


def clustered_mean(values, clusters):
    """(mean, standard error clustered by `clusters`)."""
    values = list(values)
    if not values:
        return float("nan"), float("nan")
    mean = sum(values) / len(values)
    if len(set(clusters)) < 2:
        return mean, float("nan")
    return mean, clustered_standard_error(values, list(clusters))


def interval(mean, se, z=1.96):
    """(low, high, two-sided p) for a normal approximation."""
    if not se or math.isnan(se):
        return float("nan"), float("nan"), float("nan")
    return mean - z * se, mean + z * se, math.erfc(abs(mean / se) / math.sqrt(2))


def cluster_bootstrap(rows, cluster, statistic, draws=DRAWS, seed=SEED):
    """`draws` values of statistic(rows) on samples that draw whole clusters with replacement. Rows keep their order
    within a cluster, and clusters keep chronological order, so path statistics (drawdowns) stay meaningful."""
    groups = defaultdict(list)
    for row in rows:
        groups[cluster(row)].append(row)
    keys = sorted(groups)
    generator = random.Random(seed)
    found = []
    for _ in range(draws):
        sample = sorted(generator.choice(keys) for _ in keys)
        found.append(statistic([row for key in sample for row in groups[key]]))
    return found


def percentile_interval(samples, level=0.95):
    ordered = sorted(s for s in samples if not math.isnan(s))
    if not ordered:
        return float("nan"), float("nan")
    tail = (1 - level) / 2
    return ordered[int(tail * (len(ordered) - 1))], ordered[int((1 - tail) * (len(ordered) - 1))]

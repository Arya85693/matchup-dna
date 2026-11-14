"""POST-HOC robustness, power and sensitivity analyses for the big-match myth check (working paper 1, version 2).

    python -m matchup_dna.posthoc_big_match_robustness

Version 1 (matchup_dna.posthoc_big_match) found no measurable choke or clutch trait. A review of that paper asked
what the data could have detected, and whether the result survives other reasonable choices. Every analysis here was
written after the version 1 results were known, so all of it is post-hoc. Nothing changes a model, a frozen protocol
or the version 1 output. Data, match selection, the big-match definition, the Elo baseline and the calibration are
the version 1 definitions, imported from that module.

Analyses:

A. Reproduction. The array implementation used here must reproduce every version 1 point estimate exactly.
B. Exact null tests for the spread ratios. Outcomes are simulated from the calibrated probabilities (no trait), the
   calibration is refitted on each simulated data set, and the ratio is recomputed. The p-value is the share of
   simulations with a ratio at least as large as observed. Holm's correction across the eight sets.
C. Clutch spread. The spread test on each player's big-match mean residual minus their regular-match mean residual,
   which removes form that Elo misses in every match.
D. Power and upper bounds. A clutch trait is injected: each player gets theta ~ N(0, tau^2) on the log-odds scale,
   added in big matches only and constant over the career (the easiest case to detect). For each tau the three
   version 1 tests are rerun on simulated outcomes. Power = share of simulations beyond the 95th percentile of the
   no-trait simulations. The 95% upper bound on tau is the smallest tau at which the observed statistic would be at
   or below 5% of simulated statistics.
E. Game margins. Each result is replaced by the share of games won, against an expectation fitted per
   (tour, big or regular, best of) as a fractional logit on the Elo log-odds. Same tests; the null for every spread
   ratio, the clutch ratio included, comes from permuting residuals among matches within a group.
F. Within-tournament ratings. Expectations use each player's rating updated through the earlier rounds of the
   same tournament (matchup_dna.round_aware shadow shifts) instead of the start-of-week rating.
G. Sensitivity of the persistence test: shrinkage constant 10, 50, 100; minimum 5 or 20 big matches; big matches
   = semi-finals and finals only; periods 2008-2015 against 2016 - May 2026.
H. Calibration slopes: is the big-match slope different from the regular-match slope? Wald test.
I. ATP clutch spread within one format (best of 3 only, best of 5 only), added after sections A-H showed a nominal ATP
   clutch excess: ATP big matches are mostly best of 5 and regular ones mostly best of 3, so a player who is simply
   better over five sets would look clutch. Own random stream, so sections A-H are unchanged.
"""
import json
import math
import re
import zlib

import numpy as np

from matchup_dna import posthoc_big_match as v1
from matchup_dna.elo import ELO_K, RESULTS_DIR, SURFACE_ELO_K, SURFACE_WEIGHT, blended_rating, expected_score, run_elo
from matchup_dna.experiment import Output
from matchup_dna.load import load_matches
from matchup_dna.round_aware import round_aware_features

OUTPUT = RESULTS_DIR / "phase4" / "experiments" / "posthoc_big_match_robustness.txt"
SUMMARY = RESULTS_DIR / "phase4" / "experiments" / "posthoc_big_match_robustness.json"

TOURS = ("ATP", "WTA")
TAUS = (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4)
NULL_SIMS = 2000
POWER_SIMS = 400
GAME_PERMUTATIONS = 1000
PERMUTATIONS = 1000
BOOTSTRAPS = 2000
SEED = 20261115
ALT_PERIODS = ((20080101, 20151231), (20160101, 20260531))
MAIN_PERIODS = (v1.PERIOD_1, v1.PERIOD_2)
SETS = (("finals only", "F"), ("semi-finals + finals", "SF+F"), ("all big matches", "big"), ("regular matches", "regular"))

sigmoid, logit, fit_one = v1.sigmoid, v1.logit, v1.fit_one


# ---------------------------------------------------------------- data

def games(score):
    """(games won by the match winner, games won by the loser), or None if a set cannot be read.
    A bracketed match tie-break counts as one game to the side that won it."""
    won = lost = 0
    for token in score.split():
        tiebreak = token.startswith("[")
        found = re.fullmatch(r"\[?(\d+)-(\d+)(?:\(\d+\))?\]?", token)
        if not found:
            return None
        w, l = int(found[1]), int(found[2])
        if tiebreak:
            w, l = int(w > l), int(l > w)
        won, lost = won + w, lost + l
    return (won, lost) if won + lost else None


def build(matches):
    """Arrays for every rated main-tour match in the version 1 window, oriented to the lower player id as side A."""
    surface_run = run_elo(matches, SURFACE_ELO_K)
    rounds = round_aware_features(matches, run_elo(matches, ELO_K), surface_run)
    players, cols = {}, {k: [] for k in ("tour", "big", "best_of", "round", "date", "half", "a", "b", "z", "y",
                                         "share", "z_wt", "wt_eligible")}
    for prediction in surface_run[0]:
        match = prediction["match"]
        kind = v1.classify(match)
        if kind is None or not (v1.WINDOW[0] <= match["tourney_date"] <= v1.WINDOW[1]):
            continue
        rating = {side: blended_rating(prediction[f"{side}_rating"], prediction[f"{side}_surface_rating"], SURFACE_WEIGHT)
                  for side in ("winner", "loser")}
        p_winner = expected_score(rating["winner"], rating["loser"])
        entry = rounds.get(match["key"])
        eligible = bool(entry and entry["eligible"])
        if eligible:
            p_wt = expected_score(rating["winner"] + entry["winner"]["surface_elo_shift"],
                                  rating["loser"] + entry["loser"]["surface_elo_shift"])
        else:
            p_wt = p_winner
        a_won = match["winner_id"] < match["loser_id"]
        a, b = sorted((match["winner_id"], match["loser_id"]))
        counted = games(match["score"])
        share = math.nan if counted is None else counted[0] / sum(counted)
        for key, value in (
                ("tour", match["tour"]), ("big", kind == "big"), ("best_of", match["best_of"]),
                ("round", match["round"]), ("date", match["tourney_date"]),
                ("half", zlib.crc32(f"{match['tour']}|{match['tourney_id']}".encode()) % 2),
                ("a", players.setdefault((match["tour"], a), len(players))),
                ("b", players.setdefault((match["tour"], b), len(players))),
                ("z", float(logit(p_winner if a_won else 1 - p_winner))), ("y", 1.0 if a_won else 0.0),
                ("share", share if a_won else 1 - share), ("z_wt", float(logit(p_wt if a_won else 1 - p_wt))),
                ("wt_eligible", eligible)):
            cols[key].append(value)
    data = {key: np.array(values) for key, values in cols.items()}
    data["players"] = len(players)
    return data


def big_mask(d, definition="big"):
    if definition == "big":
        return d["big"]
    if definition == "SF+F":
        return np.isin(d["round"], ("SF", "F"))
    if definition == "F":
        return d["round"] == "F"
    raise ValueError(definition)


def groups(d, big):
    """One calibration group per (tour, big or regular, best of)."""
    return (d["tour"] == "WTA") * 4 + big * 2 + (d["best_of"] == 5)


# ---------------------------------------------------------------- core statistics on arrays

def calibrate(z, y, group, mask):
    """Calibrated probabilities (NaN outside mask) and {group: (slope, se, matches)}, one slope per group."""
    p, slopes = np.full(len(z), np.nan), {}
    for g in np.unique(group[mask]):
        chosen = mask & (group == g)
        slope, se = fit_one(z[chosen], y[chosen])
        slopes[int(g)] = (slope, se, int(chosen.sum()))
        p[chosen] = sigmoid(slope * z[chosen])
    return p, slopes


def totals(d, residual, variance, mask):
    """Per player: matches, residual sum (side B's residual is minus side A's) and noise variance sum."""
    size, a, b = d["players"], d["a"][mask], d["b"][mask]
    n = (np.bincount(a, minlength=size) + np.bincount(b, minlength=size)).astype(float)
    s = np.bincount(a, residual[mask], size) - np.bincount(b, residual[mask], size)
    v = np.bincount(a, variance[mask], size) + np.bincount(b, variance[mask], size)
    return n, s, v


def spread(n, s, v, min_n=v1.MIN_BIG):
    """Same estimator as version 1's spread, on per-player totals."""
    chosen = n >= min_n
    if chosen.sum() < 3:
        return None
    n, s, v = n[chosen], s[chosen], v[chosen]
    means, noise = s / n, v / n ** 2
    centre = np.average(means, weights=n)
    observed, noise_mean = float(np.mean((means - centre) ** 2)), float(np.mean(noise))
    trait = max(0.0, observed - noise_mean)
    return {"players": int(chosen.sum()), "observed_sd": math.sqrt(observed), "noise_sd": math.sqrt(noise_mean),
            "trait_sd": math.sqrt(trait), "ratio": observed / noise_mean,
            "implied_k": float(np.mean(v / n)) / trait if trait > 0 else None}


def clutch_spread(big, regular, min_n=v1.MIN_BIG):
    """Spread of (big-match mean residual - regular-match mean residual) against its noise."""
    (nb, sb, vb), (nr, sr, vr) = big, regular
    chosen = (nb >= min_n) & (nr >= min_n)
    if chosen.sum() < 3:
        return None
    nb, sb, vb, nr, sr, vr = (x[chosen] for x in (nb, sb, vb, nr, sr, vr))
    diff, noise = sb / nb - sr / nr, vb / nb ** 2 + vr / nr ** 2
    centre = np.average(diff, weights=nb)
    observed, noise_mean = float(np.mean((diff - centre) ** 2)), float(np.mean(noise))
    return {"players": int(chosen.sum()), "observed_sd": math.sqrt(observed), "noise_sd": math.sqrt(noise_mean),
            "trait_sd": math.sqrt(max(0.0, observed - noise_mean)), "ratio": observed / noise_mean}


def pearson(x, y):
    return float(np.corrcoef(x, y)[0, 1])


def correlate(x, y, rng, reps=BOOTSTRAPS):
    """Pearson r with a percentile bootstrap interval over players (as version 1)."""
    if len(x) < 5:
        return None
    r, draws = pearson(x, y), []
    for _ in range(reps):
        pick = rng.integers(0, len(x), len(x))
        if np.std(x[pick]) > 0 and np.std(y[pick]) > 0:
            draws.append(pearson(x[pick], y[pick]))
    low, high = np.percentile(draws, [2.5, 97.5])
    return {"players": len(x), "r": r, "low": float(low), "high": float(high)}


def split_half(d, residual, variance, mask, min_n=v1.MIN_BIG):
    """Raw mean residuals in the two edition halves, for players with min_n big matches in each."""
    halves = [totals(d, residual, variance, mask & (d["half"] == h)) for h in (0, 1)]
    both = (halves[0][0] >= min_n) & (halves[1][0] >= min_n)
    x, y = (halves[h][1][both] / halves[h][0][both] for h in (0, 1))
    return x, y


def forecast(offset, y, x):
    """(beta, se, log-loss change per match) for logit P = offset + beta x."""
    if not np.any(x):
        return 0.0, math.inf, 0.0
    beta, se = fit_one(x, y, offset)
    p0, p1 = sigmoid(offset), sigmoid(offset + beta * x)
    loss = lambda p: -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
    return beta, se, float(loss(p1) - loss(p0))


def period_tests(d, y, z, tour_mask, periods, big, k=v1.SHRINK, min_n=v1.MIN_BIG, rng=None,
                 permutations=0, score_from=None):
    """The version 1 persistence test for one tour. `score_from` (residual, variance) of the earlier period replaces
    the win residuals when building the earlier scores (used for game margins). Returns correlations and forecasts."""
    group = groups(d, big)
    mask_1 = tour_mask & (d["date"] >= periods[0][0]) & (d["date"] <= periods[0][1])
    mask_2 = tour_mask & (d["date"] >= periods[1][0]) & (d["date"] <= periods[1][1])
    found = {}
    for label, mask in (("1", mask_1), ("2", mask_2)):
        p, _ = calibrate(z, y, group, mask)
        residual, variance = y - p, p * (1 - p)
        if score_from is not None:
            residual, variance = score_from(mask, big)
        big_t, reg_t = totals(d, residual, variance, mask & big), totals(d, residual, variance, mask & ~big)
        big_score, reg_score = big_t[1] / (big_t[0] + k), reg_t[1] / (reg_t[0] + k)
        # As version 1: a player with no big matches in the period has no clutch score (0), not minus their regular one.
        clutch = np.where(big_t[0] > 0, big_score - reg_score, 0.0)
        found[label] = {"p": p, "n_big": big_t[0], "big": big_score, "clutch": clutch, "regular": reg_score}
    first, second = found["1"], found["2"]
    both = (first["n_big"] >= min_n) & (second["n_big"] >= min_n)
    result = {"players": int(both.sum()), "correlations": {}, "forecasts": {}}
    for key in ("big", "clutch", "regular"):
        x, w = first[key][both], second[key][both]
        result["correlations"][key] = (correlate(x, w, rng) if rng is not None else
                                       ({"players": len(x), "r": pearson(x, w)} if len(x) >= 5 else None))
    rows = mask_2 & big
    offset, outcome = logit(second["p"][rows]), y[rows]
    a, b = d["a"][rows], d["b"][rows]
    earlier = np.flatnonzero(first["n_big"] > 0)
    for key in ("big", "clutch"):
        score = first[key]
        beta, se, change = forecast(offset, outcome, score[a] - score[b])
        entry = {"matches": int(rows.sum()), "with_history": int(np.sum((first["n_big"][a] > 0) | (first["n_big"][b] > 0))),
                 "beta": beta, "se": se, "z": beta / se if se > 0 else 0.0, "log_loss_change": change}
        if permutations:
            as_large, shuffled = 0, score.copy()
            for _ in range(permutations):
                shuffled[earlier] = rng.permutation(score[earlier])
                if forecast(offset, outcome, shuffled[a] - shuffled[b])[2] <= change:
                    as_large += 1
            entry["permutation_p"] = (as_large + 1) / (permutations + 1)
        result["forecasts"][key] = entry
    return result


def window_tests(d, y, z, tour_mask, big_definition="big", min_n=v1.MIN_BIG):
    """Spread for each set, clutch spread and split-half r for one tour over the whole window."""
    big = big_mask(d, big_definition)
    p, slopes = calibrate(z, y, groups(d, big), tour_mask)
    residual, variance = y - p, p * (1 - p)
    out = {"slopes": slopes, "spread": {}}
    for label, definition in SETS:
        chosen = ~big if definition == "regular" else big_mask(d, definition)
        out["spread"][label] = spread(*totals(d, residual, variance, tour_mask & chosen), min_n)
    out["clutch"] = clutch_spread(totals(d, residual, variance, tour_mask & big),
                                  totals(d, residual, variance, tour_mask & ~big), min_n)
    out["split_half"] = split_half(d, residual, variance, tour_mask & big, min_n)
    return out


# ---------------------------------------------------------------- game margins

def share_expectation(d, tour_mask, big):
    """Expected share of games for side A: fractional logit on the Elo log-odds, one slope per group.
    Returns (residual, variance) arrays where variance is the group's mean squared residual."""
    has = ~np.isnan(d["share"])
    group = groups(d, big)
    residual, variance = np.full(len(group), np.nan), np.full(len(group), np.nan)
    for g in np.unique(group[tour_mask & has]):
        chosen = tour_mask & has & (group == g)
        slope, _ = fit_one(d["z"][chosen], d["share"][chosen])
        residual[chosen] = d["share"][chosen] - sigmoid(slope * d["z"][chosen])
        variance[chosen] = np.mean(residual[chosen] ** 2)
    return residual, variance


def game_sets(d, has):
    """{label: mask} for the game-margin spread sets."""
    return {label: has & (~d["big"] if definition == "regular" else big_mask(d, definition)) for label, definition in SETS}


def game_ratios(d, residual, variance, has, min_n=v1.MIN_BIG):
    found = {label: spread(*totals(d, residual, variance, chosen), min_n) for label, chosen in game_sets(d, has).items()}
    found["clutch"] = clutch_spread(totals(d, residual, variance, has & d["big"]),
                                    totals(d, residual, variance, has & ~d["big"]), min_n)
    return found


def permuted_games(d, residual, variance, has, rng, reps=GAME_PERMUTATIONS):
    """Null distributions of every game-margin spread ratio (and the clutch ratio) when residuals are shuffled among
    matches within each (tour, big or regular, best of) group."""
    group = groups(d, d["big"])
    members = [np.flatnonzero(has & (group == g)) for g in np.unique(group[has])]
    draws = []
    for _ in range(reps):
        shuffled = residual.copy()
        for index in members:
            shuffled[index] = rng.permutation(residual[index])
        draws.append({k: (v["ratio"] if v else math.nan) for k, v in game_ratios(d, shuffled, variance, has).items()})
    return {k: np.array([draw[k] for draw in draws]) for k in draws[0]}


# ---------------------------------------------------------------- simulations

def simulate(d, tour_mask, p_base, tau, rng, periods=MAIN_PERIODS):
    """Statistics of the version 1 tests on outcomes simulated from p_base, with a clutch trait of sd tau added in
    big matches."""
    big = d["big"]
    theta = rng.normal(0.0, tau, d["players"]) if tau > 0 else np.zeros(d["players"])
    shift = np.where(big, theta[d["a"]] - theta[d["b"]], 0.0)
    y = np.zeros(len(big))
    y[tour_mask] = (rng.random(tour_mask.sum()) < sigmoid(logit(p_base[tour_mask]) + shift[tour_mask])).astype(float)
    w = window_tests(d, y, d["z"], tour_mask)
    x, h = w["split_half"]
    period = period_tests(d, y, d["z"], tour_mask, periods, big)
    stats = {f"ratio {label}": (w["spread"][label] or {}).get("ratio", math.nan) for label, _ in SETS}
    stats.update({"clutch ratio": w["clutch"]["ratio"], "split-half r": pearson(x, h),
                  "period r big": period["correlations"]["big"]["r"],
                  "period r clutch": period["correlations"]["clutch"]["r"],
                  "forecast z big": period["forecasts"]["big"]["z"],
                  "forecast z clutch": period["forecasts"]["clutch"]["z"]})
    return stats


def tail_p(null, observed):
    null = null[~np.isnan(null)]
    return float((np.sum(null >= observed) + 1) / (len(null) + 1))


def holm(pvalues):
    """Holm-adjusted p-values, same order as given."""
    order = np.argsort(pvalues)
    adjusted, running = np.empty(len(pvalues)), 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(pvalues) - rank) * pvalues[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def upper_bound(taus, below):
    """Smallest tau where P(statistic <= observed | tau) falls under 0.05, by linear interpolation between grid
    points. `below[i]` is that probability at taus[i] (taus[0] = 0). None if it never falls under 0.05."""
    for i in range(1, len(taus)):
        if below[i] < 0.05:
            if below[i - 1] <= 0.05:
                return taus[i - 1]
            t = (below[i - 1] - 0.05) / (below[i - 1] - below[i])
            return taus[i - 1] + t * (taus[i] - taus[i - 1])
    return None


def evens(tau):
    """Win probability against an equal opponent for a player one trait sd above average, in points over 50."""
    return 100 * (float(sigmoid(tau)) - 0.5)


def format_clutch(d, mask, rng, sims=NULL_SIMS):
    """Clutch spread (wins: exact simulation p; games: permutation p) on the matches in `mask` only."""
    big, y, z = d["big"], d["y"], d["z"]
    p, _ = calibrate(z, y, groups(d, big), mask)

    def ratio(outcome, probability):
        residual, variance = outcome - probability, probability * (1 - probability)
        found = clutch_spread(totals(d, residual, variance, mask & big), totals(d, residual, variance, mask & ~big))
        return found

    wins = ratio(y, p)
    null = []
    for _ in range(sims):
        simulated = np.zeros(len(y))
        simulated[mask] = (rng.random(mask.sum()) < p[mask]).astype(float)
        refit, _ = calibrate(z, simulated, groups(d, big), mask)
        found = ratio(simulated, refit)
        null.append(found["ratio"] if found else math.nan)
    wins["p"] = tail_p(np.array(null), wins["ratio"])

    has = mask & ~np.isnan(d["share"])
    residual, variance = share_expectation(d, mask, big)
    games_found = game_ratios(d, residual, variance, has)["clutch"]
    games_found["p"] = tail_p(permuted_games(d, residual, variance, has, rng)["clutch"], games_found["ratio"])
    return {"big_matches": int((mask & big).sum()), "regular_matches": int((mask & ~big).sum()), "wins": wins,
            "games": games_found}


# ---------------------------------------------------------------- report

def main():
    out = Output()
    rng = np.random.default_rng(SEED)
    d = build(load_matches())
    y, z = d["y"], d["z"]
    summary = {"definitions": {"taus": TAUS, "null_sims": NULL_SIMS, "power_sims": POWER_SIMS,
                               "permutations": PERMUTATIONS, "game_permutations": GAME_PERMUTATIONS, "bootstraps": BOOTSTRAPS, "seed": SEED,
                               "alt_periods": ALT_PERIODS},
               "reproduction": {}, "slope_tests": {}, "null": {}, "power": {}, "games": {}, "within": {},
               "sensitivity": {}}
    out("POST-HOC robustness, power and sensitivity for the big-match myth check (version 2; written after the")
    out("version 1 results were known). Version 1 definitions throughout.")
    out()

    # A. reproduction of version 1 point estimates
    published = json.loads(v1.SUMMARY.read_text(encoding="utf-8")) if v1.SUMMARY.exists() else None
    out(f"A. REPRODUCTION: {len(y):,} matches, {int(d['big'].sum()):,} big (version 1: 131,649 and 14,071).")
    worst = 0.0
    base = {}
    for tour in TOURS:
        mask = d["tour"] == tour
        base[tour] = {"window": window_tests(d, y, z, mask),
                      "period": period_tests(d, y, z, mask, MAIN_PERIODS, d["big"], rng=rng,
                                             permutations=PERMUTATIONS)}
        if published:
            for label, _ in SETS:
                worst = max(worst, abs(base[tour]["window"]["spread"][label]["ratio"]
                                       - published["spread"][f"{tour} {label}"]["ratio"]))
            x, h = base[tour]["window"]["split_half"]
            worst = max(worst, abs(pearson(x, h) - published["split_half"][tour]["r"]))
            for key, name in (("big", "big-match score"), ("clutch", "clutch score"), ("regular", "regular-match score")):
                worst = max(worst, abs(base[tour]["period"]["correlations"][key]["r"]
                                       - published["period_split"][tour][name]["r"]))
            for key, name in (("big", "big-match score"), ("clutch", "clutch score")):
                worst = max(worst, abs(base[tour]["period"]["forecasts"][key]["beta"]
                                       - published["period_split"][tour][f"forecast with {name}"]["beta"]))
    summary["reproduction"] = {"matches": len(y), "big": int(d["big"].sum()), "checked": published is not None,
                               "largest_difference": worst}
    out(f"   largest difference from the version 1 point estimates: {worst:.2e}" if published else
        "   version 1 output not found; run matchup_dna.posthoc_big_match first to check.")
    out()

    # H. calibration slopes
    out("H. CALIBRATION SLOPES, big against regular, with Wald tests (2000 - May 2026)")
    for tour in TOURS:
        slopes = base[tour]["window"]["slopes"]
        offset = 4 if tour == "WTA" else 0
        for bo in (3, 5):
            big_key, reg_key = offset + 2 + (bo == 5), offset + (bo == 5)
            if big_key not in slopes or reg_key not in slopes:
                continue
            (bb, sb, nb), (br, sr, nr) = slopes[big_key], slopes[reg_key]
            zval = (bb - br) / math.sqrt(sb ** 2 + sr ** 2)
            pval = math.erfc(abs(zval) / math.sqrt(2))
            summary["slope_tests"][f"{tour} bo{bo}"] = {"big": bb, "big_se": sb, "big_n": nb, "regular": br,
                                                         "regular_se": sr, "regular_n": nr, "z": zval, "p": pval}
            out(f"   {tour} best of {bo}: big {bb:.3f} (se {sb:.3f}, n {nb:,}) regular {br:.3f} (se {sr:.3f}, "
                f"n {nr:,}); difference {bb - br:+.3f}, z {zval:+.2f}, p {pval:.4f}")
    out()

    # B, C, D. simulations
    out(f"B-D. SIMULATIONS: {NULL_SIMS:,} with no trait, {POWER_SIMS} at each trait size tau (log-odds sd, big matches")
    out("   only, constant over the career). Calibration refitted on every simulated data set.")
    for tour in TOURS:
        mask = d["tour"] == tour
        p_base, _ = calibrate(z, y, groups(d, d["big"]), mask)
        null = [simulate(d, mask, p_base, 0.0, rng) for _ in range(NULL_SIMS)]
        keys = list(null[0])
        null = {k: np.array([s[k] for s in null]) for k in keys}
        w, period = base[tour]["window"], base[tour]["period"]
        x, h = w["split_half"]
        observed = {f"ratio {label}": w["spread"][label]["ratio"] for label, _ in SETS}
        observed.update({"clutch ratio": w["clutch"]["ratio"], "split-half r": pearson(x, h),
                         "period r big": period["correlations"]["big"]["r"],
                         "period r clutch": period["correlations"]["clutch"]["r"],
                         "forecast z big": period["forecasts"]["big"]["z"],
                         "forecast z clutch": period["forecasts"]["clutch"]["z"]})
        pvalues = {k: tail_p(null[k], observed[k]) for k in keys}
        summary["null"][tour] = {"observed": observed, "p": pvalues,
                                 "critical": {k: float(np.nanpercentile(null[k], 95)) for k in keys},
                                 "clutch": w["clutch"]}
        out(f"   {tour} exact null tests (one-sided, share of no-trait simulations at least as large):")
        for k in keys:
            out(f"      {k:<34} observed {observed[k]:+.3f}  null 95th pct {summary['null'][tour]['critical'][k]:+.3f}"
                f"  p {pvalues[k]:.3f}")

        power = {k: [] for k in keys}
        below = {k: [float(np.mean(null[k][~np.isnan(null[k])] <= observed[k]))] for k in keys}
        for tau in TAUS:
            sims = [simulate(d, mask, p_base, tau, rng) for _ in range(POWER_SIMS)]
            for k in keys:
                values = np.array([s[k] for s in sims])
                power[k].append(float(np.mean(values > summary["null"][tour]["critical"][k])))
                below[k].append(float(np.mean(values <= observed[k])))
        grid = (0.0,) + TAUS
        bounds = {k: upper_bound(grid, below[k]) for k in keys}
        summary["power"][tour] = {"taus": list(TAUS), "power": power, "below": below, "upper_bound": bounds}
        out(f"   {tour} power at each tau (tau {', '.join(f'{t:.2f}' for t in TAUS)}; "
            f"evens edge {', '.join(f'{evens(t):.1f}' for t in TAUS)} points):")
        for k in keys:
            bound = bounds[k]
            text = "none in grid" if bound is None else f"{bound:.3f} ({evens(bound):.1f} points)"
            out(f"      {k:<20} power {' '.join(f'{v:.2f}' for v in power[k])}   95% upper bound on tau {text}")
    out()

    # B. Holm across the spread sets
    flat = [(tour, label) for tour in TOURS for label, _ in SETS]
    adjusted = holm([summary["null"][t]["p"][f"ratio {label}"] for t, label in flat])
    summary["holm"] = {f"{t} {label}": a for (t, label), a in zip(flat, adjusted)}
    out("   Holm-adjusted spread p-values: " + "; ".join(f"{t} {label} {a:.3f}" for (t, label), a in zip(flat, adjusted)))
    out()

    # E. game margins
    out("E. GAME MARGINS: share of games won against a fitted expectation (2000 - May 2026)")
    for tour in TOURS:
        mask = d["tour"] == tour
        has = mask & ~np.isnan(d["share"])
        residual, variance = share_expectation(d, mask, d["big"])
        found = {"matches": int(has.sum()), "missing": int(mask.sum() - has.sum()),
                 "per_match_sd": float(np.sqrt(np.nanmean(residual[has] ** 2)))}
        ratios, null = game_ratios(d, residual, variance, has), permuted_games(d, residual, variance, has, rng)
        for key in ratios:
            ratios[key]["p"] = tail_p(null[key], ratios[key]["ratio"])
        found["clutch"] = ratios.pop("clutch")
        found["spread"] = ratios
        x, h = split_half(d, residual, variance, has & d["big"])
        found["split_half"] = correlate(x, h, rng)
        r = found["split_half"]["r"]
        found["split_half"]["spearman_brown"] = 2 * r / (1 + r)

        def from_games(period_mask, big):
            res, var = share_expectation(d, period_mask, big)
            return np.nan_to_num(res), np.nan_to_num(var)

        found["period"] = period_tests(d, y, z, mask, MAIN_PERIODS, d["big"], rng=rng, permutations=PERMUTATIONS,
                                       score_from=from_games)
        summary["games"][tour] = found
        out(f"   {tour}: {found['matches']:,} matches with a readable score ({found['missing']} without); "
            f"residual sd per match {100 * found['per_match_sd']:.1f} points")
        for label, _ in SETS:
            s = found["spread"][label]
            out(f"      spread {label:<22} players {s['players']:>4} ratio {s['ratio']:.2f} trait sd "
                f"{100 * s['trait_sd']:.2f} points  permutation p {s['p']:.3f}")
        c = found["clutch"]
        out(f"      clutch spread ({c['players']} players) ratio {c['ratio']:.2f}  permutation p {c['p']:.3f}")
        sh = found["split_half"]
        out(f"      split-half r {sh['r']:+.3f} (95% {sh['low']:+.3f} to {sh['high']:+.3f}), {sh['players']} players")
        pr = found["period"]
        for key in ("big", "clutch", "regular"):
            c = pr["correlations"][key]
            out(f"      period r {key:<8} {c['r']:+.3f} (95% {c['low']:+.3f} to {c['high']:+.3f}), {pr['players']} players")
        for key in ("big", "clutch"):
            f = pr["forecasts"][key]
            out(f"      forecast of later big-match wins with the earlier {key} game score: beta {f['beta']:+.2f} "
                f"(se {f['se']:.2f}), log loss change {f['log_loss_change']:+.5f}, permutation p {f['permutation_p']:.3f}")
    out()

    # F. within-tournament ratings
    out("F. WITHIN-TOURNAMENT RATINGS: expectations updated through earlier rounds of the same event")
    for tour in TOURS:
        mask = d["tour"] == tour
        w = window_tests(d, y, d["z_wt"], mask)
        x, h = w["split_half"]
        split = correlate(x, h, rng)
        period = period_tests(d, y, d["z_wt"], mask, MAIN_PERIODS, d["big"], rng=rng, permutations=PERMUTATIONS)
        eligible = float(np.mean(d["wt_eligible"][mask & d["big"]]))
        summary["within"][tour] = {"eligible_share_big": eligible, "spread": w["spread"], "clutch": w["clutch"],
                                   "split_half": split, "period": period}
        out(f"   {tour}: {100 * eligible:.1f}% of big matches have a complete earlier-round record (others keep the "
            "start-of-week rating)")
        out("      spread ratios: " + "; ".join(f"{label} {w['spread'][label]['ratio']:.2f}" for label, _ in SETS)
            + f"; clutch {w['clutch']['ratio']:.2f}")
        out(f"      split-half r {split['r']:+.3f} (95% {split['low']:+.3f} to {split['high']:+.3f})")
        for key in ("big", "clutch"):
            f, c = period["forecasts"][key], period["correlations"][key]
            out(f"      period r {key:<7} {c['r']:+.3f}; forecast beta {f['beta']:+.2f} (se {f['se']:.2f}), "
                f"permutation p {f['permutation_p']:.3f}")
    out()

    # G. sensitivity
    out("G. SENSITIVITY of the persistence test (one choice changed at a time; version 1 = shrinkage 20, minimum 10,")
    out("   all big matches, 2012-2018 against 2019 - May 2026)")
    variants = [("version 1 settings", {}), ("shrinkage 10", {"k": 10}), ("shrinkage 50", {"k": 50}),
                ("shrinkage 100", {"k": 100}), ("minimum 5", {"min_n": 5}), ("minimum 20", {"min_n": 20}),
                ("semi-finals and finals only", {"big": "SF+F"}), ("periods 2008-2015 / 2016-2026", {"periods": ALT_PERIODS})]
    for tour in TOURS:
        mask = d["tour"] == tour
        summary["sensitivity"][tour] = {}
        for label, change in variants:
            if not change:
                found = base[tour]["period"]
            else:
                found = period_tests(d, y, z, mask, change.get("periods", MAIN_PERIODS),
                                     big_mask(d, change.get("big", "big")), k=change.get("k", v1.SHRINK),
                                     min_n=change.get("min_n", v1.MIN_BIG), rng=rng, permutations=PERMUTATIONS)
            summary["sensitivity"][tour][label] = found
            fb, fc = found["forecasts"]["big"], found["forecasts"]["clutch"]
            cc = found["correlations"]["clutch"]
            out(f"   {tour} {label:<32} players {found['players']:>3}  clutch r {cc['r']:+.3f} "
                f"({cc['low']:+.2f} to {cc['high']:+.2f})  big beta {fb['beta']:+.2f} p {fb['permutation_p']:.3f}  "
                f"clutch beta {fc['beta']:+.2f} p {fc['permutation_p']:.3f}")
    out()

    # I. ATP clutch spread within one format
    out("I. ATP CLUTCH SPREAD WITHIN ONE FORMAT: ATP big matches are mostly best of 5, regular ones mostly best of 3, so")
    out("   a player who is simply better over five sets would look clutch. Big against regular within each format.")
    format_rng = np.random.default_rng(SEED + 1)
    summary["format"] = {}
    for bo in (3, 5):
        mask = (d["tour"] == "ATP") & (d["best_of"] == bo)
        found = format_clutch(d, mask, format_rng)
        summary["format"][f"ATP bo{bo}"] = found
        w, g = found["wins"], found["games"]
        out(f"   best of {bo}: {found['big_matches']:,} big and {found['regular_matches']:,} regular matches")
        out(f"      wins:  clutch ratio {w['ratio']:.2f} ({w['players']} players), exact p {w['p']:.3f}")
        out(f"      games: clutch ratio {g['ratio']:.2f} ({g['players']} players), permutation p {g['p']:.3f}")
    out()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, indent=2, default=to_json) + "\n", encoding="utf-8")
    print(f"Saved {OUTPUT} and {SUMMARY}")


def to_json(value):
    if isinstance(value, np.ndarray):
        return None                                   # per-player arrays are working data, not results
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    return str(value)


if __name__ == "__main__":
    main()

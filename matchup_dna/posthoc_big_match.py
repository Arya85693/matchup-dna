"""POST-HOC descriptive analysis, not part of any frozen protocol: is "big-match performance" a stable player trait?

    python -m matchup_dna.posthoc_big_match

The question: do some players win big matches (semi-finals, finals, late Slam and Masters rounds) more or less
often than their strength says, and does that carry over from one period of their career to the next? If it does
not persist, it cannot help a forecast, and no feature is worth building. Nothing here changes a model, a frozen
protocol or the website. It reads Sackmann's tour-level files only (to 25 May 2026), so no sealed outcome is used.

Definitions, fixed before any result was seen:

- Main-tour events only: ATP levels G, M, A, F, O; WTA levels G, PM, P, I, W, T1-T5, F, O. Davis Cup, Billie Jean
  King Cup, team events, exhibitions and the bronze-medal match are left out. Rated matches only (completed,
  best of 3 or 5), as in matchup_dna.elo.
- A big match is: any semi-final or final; a Slam fourth round or quarter-final; a Masters quarter-final (ATP M,
  WTA PM, and WTA Tier I before 2009); any match at the season-ending Finals. Every other main-tour match is a
  regular match.
- Strength is the project's canonical surface-blended Elo (SURFACE_ELO_K, SURFACE_WEIGHT), taken at the start of
  the tournament week, never refitted.
- Plain Elo is known to be too cautious in best-of-5 and can be off in later rounds. If that were left in, players
  who are usually favourites in Slams would look "clutch" for a reason that has nothing to do with pressure. So
  Elo is recalibrated with one slope per (tour, big or regular, best of 3 or 5), fitted on the matches of the
  window being analysed: P(win) = sigmoid(slope x Elo log-odds).
- A player's residual in a match is (1 if they won, else 0) minus that calibrated probability. A player's
  big-match score is the sum of big-match residuals divided by (matches + 20): heavy shrinkage toward zero, so
  20 big matches count as half signal, half "no effect". The clutch score is the big-match score minus the same
  score on regular matches, so a player Elo underrates everywhere (a fast riser) is not counted as clutch.

Tests, all stated here before the run:

1. Spread. Over 2000 - May 2026, for players with at least 10 big matches, how much of the variation in raw
   big-match residuals is more than coin-flip noise? The excess is the variance of a true trait (empirical Bayes).
2. Split-half. Big matches from 2000 - May 2026 are split into two halves by tournament edition (CRC32 of the
   tourney_id, odd or even). Correlation of the two halves' raw residual means across players with at least 10
   big matches in each half. This asks whether a trait exists at all, ignoring changes over a career.
3. Period split (the persistence check). Scores from 2012-2018 against 2019 - May 2026, for players with at least
   10 big matches in each. Two measures: the correlation of shrunk scores (bootstrap over players), and whether
   2012-2018 scores improve the calibrated Elo forecast of the 2019 - May 2026 big matches: logit P = calibrated
   log-odds + beta x (score A - score B), one parameter fitted by maximum likelihood. The p-value comes from 1,000
   permutations of the 2012-2018 scores among players, which respects that one player appears in many matches.

The players the brief named (and a few others) are listed with actual against expected wins, for illustration.

Version 3 corrections (16 November 2026, after an audit; the version 1 and 2 results used the definitions above as
implemented then):

- Window end. Sackmann's last edition in the snapshot is Roland Garros 2026 (tourney_date 20260525). Its later rounds
  were played in June 2026, which the project keeps sealed, but the old window (to 20260531 by tourney_date) included
  them. The window and the later period now end on 20260524, so no edition that ran into June is used.
- Team events and exhibitions coded as ordinary tour events (level A) are left out, as the definitions always said:
  ATP Cup, United Cup, World Team Cup (Dusseldorf, round robin, 2000-2012), Laver Cup. So are the Next Gen ATP Finals
  (an under-21 event with experimental scoring) and WTA 125 events, which are below the main tour.
- The season-ending Finals are identified by event, not by level code: the code F also covers the WTA Tournament of
  Champions (2009-2014) and WTA Elite Trophy (2015-2019), second-tier year-end events now treated as ordinary tour
  events (their semi-finals and finals are big, their group matches regular), and the 2015 WTA Finals and 2023 ATP
  Finals carry other codes.
- The WTA tier counted alongside ATP Masters quarter-finals is now set by event and year (WTA_TOP_TIER), because the
  level codes are not consistent: Premier Mandatory events are coded P in 2016 and 2020-2022, and from 2023 the code
  PM covers the whole WTA 1000 tier. The tier is the highest below the Grand Slams in each era: Tier I to 2008,
  Premier Mandatory and Premier 5 from 2009 to 2020, WTA 1000 from 2021.
"""
import json
import re
import math
import zlib
from collections import defaultdict

import numpy as np

from matchup_dna.elo import RESULTS_DIR, SURFACE_ELO_K, SURFACE_WEIGHT, run_elo, win_probability
from matchup_dna.experiment import Output
from matchup_dna.load import load_matches

OUTPUT = RESULTS_DIR / "phase4" / "experiments" / "posthoc_big_match.txt"
SUMMARY = RESULTS_DIR / "phase4" / "experiments" / "posthoc_big_match.json"

TOUR_LEVELS = {
    "ATP": {"G", "M", "A", "F", "O"},
    "WTA": {"G", "PM", "P", "I", "W", "T1", "T2", "T3", "T4", "T5", "F", "O"},
}
DRAW_ROUNDS = {"R128", "R64", "R32", "R16", "QF", "SF", "F", "RR"}

# Version 3 (see the docstring). Names as spelled in Sackmann's files.
EXCLUDED_NAMES = re.compile(r"atp cup|united cup|laver cup|next ?gen|\b125\b", re.IGNORECASE)
SEASON_FINALS = {
    "ATP": {"Masters Cup", "Tour Finals"},
    "WTA": {"WTA Tour Championships", "WTA Championships", "WTA Finals", "Singapore", "Shenzhen Finals",
            "Guadalajara Finals", "Fort Worth Finals", "Cancun Finals", "Riyadh Finals"},
}
_MANDATORY = ("Indian Wells", "Miami", "Madrid", "Beijing")
_CANADA = ("Toronto", "Montreal")
WTA_TOP_TIER = {
    # 2009-2020: Premier Mandatory + Premier 5 (events actually played). 2021 on: WTA 1000.
    2009: {*_MANDATORY, "Dubai", "Rome", "Cincinnati", *_CANADA, "Tokyo"},
    2010: {*_MANDATORY, "Dubai", "Rome", "Cincinnati", *_CANADA, "Tokyo"},
    2011: {*_MANDATORY, "Dubai", "Rome", "Cincinnati", *_CANADA, "Tokyo"},
    2012: {*_MANDATORY, "Doha", "Rome", "Cincinnati", *_CANADA, "Tokyo"},
    2013: {*_MANDATORY, "Doha", "Rome", "Cincinnati", *_CANADA, "Tokyo"},
    2014: {*_MANDATORY, "Doha", "Rome", "Cincinnati", *_CANADA, "Wuhan"},
    2015: {*_MANDATORY, "Dubai", "Rome", "Cincinnati", *_CANADA, "Wuhan"},
    2016: {*_MANDATORY, "Doha", "Rome", "Cincinnati", *_CANADA, "Wuhan"},
    2017: {*_MANDATORY, "Dubai", "Rome", "Cincinnati", *_CANADA, "Wuhan"},
    2018: {*_MANDATORY, "Doha", "Rome", "Cincinnati", *_CANADA, "Wuhan"},
    2019: {*_MANDATORY, "Dubai", "Rome", "Cincinnati", *_CANADA, "Wuhan"},
    2020: {"Doha", "Rome", "Cincinnati"},
    2021: {"Dubai", "Miami", "Madrid", "Rome", *_CANADA, "Cincinnati", "Indian Wells"},
    2022: {"Doha", "Indian Wells", "Miami", "Madrid", "Rome", *_CANADA, "Cincinnati", "Guadalajara 2"},
    2023: {"Dubai", "Indian Wells", "Miami", "Madrid", "Rome", *_CANADA, "Cincinnati", "Guadalajara", "Beijing"},
    2024: {"Doha", "Dubai", "Indian Wells", "Miami", "Madrid", "Rome", *_CANADA, "Cincinnati", "Beijing", "Wuhan"},
    2025: {"Doha", "Dubai", "Indian Wells", "Miami", "Madrid", "Rome", *_CANADA, "Cincinnati", "Beijing", "Wuhan"},
    2026: {"Doha", "Dubai", "Indian Wells", "Miami", "Madrid", "Rome"},
}

SHRINK = 20
MIN_BIG = 10
LAST_DAY = 20260524           # the last tourney_date used: Roland Garros 2026 (20260525) ran into the sealed June
WINDOW = (20000101, LAST_DAY)
PERIOD_1 = (20120101, 20181231)
PERIOD_2 = (20190101, LAST_DAY)
PERMUTATIONS = 1000
BOOTSTRAPS = 2000
SEED = 20261114

NAMED = (
    ("WTA", "Aryna Sabalenka"), ("ATP", "Daniil Medvedev"), ("ATP", "Alexander Zverev"), ("ATP", "Jannik Sinner"),
    ("ATP", "Carlos Alcaraz"), ("ATP", "Novak Djokovic"), ("ATP", "Rafael Nadal"), ("ATP", "Roger Federer"),
    ("ATP", "Andy Murray"), ("ATP", "Stefanos Tsitsipas"), ("WTA", "Iga Swiatek"), ("WTA", "Coco Gauff"),
    ("WTA", "Elena Rybakina"), ("WTA", "Serena Williams"),
)


# ---------------------------------------------------------------- which matches count

def excluded_event(match):
    """Team events, exhibitions, the Next Gen Finals and WTA 125 events, whatever their level code."""
    name = match["tourney_name"].strip()
    if EXCLUDED_NAMES.search(name):
        return True
    return match["tour"] == "ATP" and name == "Dusseldorf" and match["tourney_date"] <= 20121231  # World Team Cup


def is_finals(match):
    """The season-ending Finals (ATP Finals, WTA Finals), identified by event name rather than level code."""
    name = match["tourney_name"].strip()
    if name not in SEASON_FINALS[match["tour"]]:
        return False
    return name != "Singapore" or match["tourney_level"] == "F"   # the WTA Finals were "Singapore" in 2016-2018


def top_tier(match):
    """The highest tier below the Grand Slams: ATP Masters; WTA Tier I to 2008, then WTA_TOP_TIER by year."""
    if match["tour"] == "ATP":
        return match["tourney_level"] == "M"
    year = match["tourney_date"] // 10000
    if year <= 2008:
        return match["tourney_level"] == "T1"
    return match["tourney_name"].strip() in WTA_TOP_TIER.get(year, ())


def classify(match):
    """"big", "regular", or None (not a main-tour draw match)."""
    tour, level, round_name = match["tour"], match["tourney_level"], match["round"]
    if level not in TOUR_LEVELS.get(tour, ()) or round_name not in DRAW_ROUNDS or excluded_event(match):
        return None
    if is_finals(match) or round_name in ("SF", "F"):
        return "big"
    if level == "G" and round_name in ("R16", "QF"):
        return "big"
    if top_tier(match) and round_name == "QF":
        return "big"
    return "regular"


def match_rows(matches):
    """One row per rated main-tour match, oriented to the lower player id as side A so the label varies."""
    predictions, _ = run_elo(matches, SURFACE_ELO_K)
    rows = []
    for prediction in predictions:
        match = prediction["match"]
        kind = classify(match)
        if kind is None:
            continue
        p_winner = win_probability(prediction, SURFACE_WEIGHT)
        a_won = match["winner_id"] < match["loser_id"]
        a, b = sorted((match["winner_id"], match["loser_id"]))
        rows.append({
            "tour": match["tour"], "date": match["tourney_date"], "tourney_id": match["tourney_id"],
            "round": match["round"], "kind": kind, "best_of": match["best_of"],
            "a": (match["tour"], a), "b": (match["tour"], b),
            "p_a": p_winner if a_won else 1 - p_winner, "y": 1.0 if a_won else 0.0,
        })
    return rows


def within(rows, period):
    start, end = period
    return [row for row in rows if start <= row["date"] <= end]


# ---------------------------------------------------------------- calibration and residuals

def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1 / (1 + np.exp(-np.asarray(z, dtype=float)))


def fit_one(x, y, offset=None, iterations=50):
    """Maximum-likelihood coefficient c in P = sigmoid(offset + c x), by Newton's method. Returns (c, se)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    offset = np.zeros_like(x) if offset is None else np.asarray(offset, dtype=float)
    c = 0.0
    for _ in range(iterations):
        p = sigmoid(offset + c * x)
        gradient = np.sum((y - p) * x)
        information = np.sum(p * (1 - p) * x * x)
        if information <= 0:
            return 0.0, math.inf
        step = gradient / information
        c += step
        if abs(step) < 1e-10:
            break
    p = sigmoid(offset + c * x)
    return c, 1 / math.sqrt(np.sum(p * (1 - p) * x * x))


def calibrate(rows):
    """Calibrated P(A wins) for each row: one Elo log-odds slope per (tour, kind, best_of), fitted on `rows`.
    Returns (probabilities, {group: slope})."""
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[(row["tour"], row["kind"], row["best_of"])].append(index)
    z = logit([row["p_a"] for row in rows])
    y = np.array([row["y"] for row in rows])
    calibrated, slopes = np.empty(len(rows)), {}
    for group, indexes in groups.items():
        indexes = np.array(indexes)
        slope, _ = fit_one(z[indexes], y[indexes])
        slopes[group] = slope
        calibrated[indexes] = sigmoid(slope * z[indexes])
    return calibrated, slopes


def player_stats(rows, probabilities, kind=None, rounds=None):
    """{player: [matches, wins, expected wins, residual variance]} over rows of one kind (or all)."""
    stats = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    for row, p in zip(rows, probabilities):
        if (kind and row["kind"] != kind) or (rounds and row["round"] not in rounds):
            continue
        for player, won, expected in ((row["a"], row["y"], p), (row["b"], 1 - row["y"], 1 - p)):
            entry = stats[player]
            entry[0] += 1
            entry[1] += won
            entry[2] += expected
            entry[3] += expected * (1 - expected)
    return dict(stats)


def shrunk(entry, k=SHRINK):
    """Residual sum / (matches + k): zero for a player with no matches, half-weight at k matches."""
    if entry is None:
        return 0.0
    return (entry[1] - entry[2]) / (entry[0] + k)


def scores(stats_big, stats_regular, k=SHRINK):
    """({player: shrunk big-match score}, {player: clutch score = big minus regular})."""
    big = {player: shrunk(entry, k) for player, entry in stats_big.items()}
    clutch = {player: value - shrunk(stats_regular.get(player), k) for player, value in big.items()}
    return big, clutch


# ---------------------------------------------------------------- the three tests

def spread(stats, min_n=MIN_BIG):
    """Empirical Bayes split of the variance of players' raw mean residuals into coin-flip noise and a trait.
    Returns a dict with the trait standard deviation in win-probability points and the implied shrinkage k."""
    chosen = [entry for entry in stats.values() if entry[0] >= min_n]
    if len(chosen) < 3:
        return None
    means = np.array([(e[1] - e[2]) / e[0] for e in chosen])
    noise = np.array([e[3] / e[0] ** 2 for e in chosen])
    weights = np.array([e[0] for e in chosen], dtype=float)
    centre = np.average(means, weights=weights)
    observed = float(np.mean((means - centre) ** 2))
    noise_mean = float(np.mean(noise))
    trait = max(0.0, observed - noise_mean)
    per_match_variance = float(np.mean([e[3] / e[0] for e in chosen]))
    return {
        "players": len(chosen), "observed_sd": math.sqrt(observed), "noise_sd": math.sqrt(noise_mean),
        "trait_sd": math.sqrt(trait), "ratio": observed / noise_mean,
        "implied_k": per_match_variance / trait if trait > 0 else math.inf,
    }


def correlate(pairs, rng, reps=BOOTSTRAPS):
    """Pearson correlation of (x, y) pairs with a percentile bootstrap interval over players."""
    if len(pairs) < 5:
        return None
    data = np.array(pairs, dtype=float)
    r = float(np.corrcoef(data[:, 0], data[:, 1])[0, 1])
    draws = []
    for _ in range(reps):
        sample = data[rng.integers(0, len(data), len(data))]
        if np.std(sample[:, 0]) > 0 and np.std(sample[:, 1]) > 0:
            draws.append(np.corrcoef(sample[:, 0], sample[:, 1])[0, 1])
    low, high = np.percentile(draws, [2.5, 97.5])
    return {"players": len(data), "r": r, "low": float(low), "high": float(high)}


def edition_half(row):
    return zlib.crc32(f"{row['tour']}|{row['tourney_id']}".encode()) % 2


def split_half(rows, probabilities, rng, min_n=MIN_BIG):
    halves = [defaultdict(lambda: [0, 0.0, 0.0, 0.0]) for _ in range(2)]
    for half in (0, 1):
        chosen = [(r, p) for r, p in zip(rows, probabilities) if r["kind"] == "big" and edition_half(r) == half]
        found = player_stats([r for r, _ in chosen], [p for _, p in chosen], "big")
        halves[half].update(found)
    pairs = []
    # Sorted so the bootstrap draws do not depend on Python's per-process string hashing (PYTHONHASHSEED).
    for player in sorted(set(halves[0]) & set(halves[1])):
        first, second = halves[0][player], halves[1][player]
        if first[0] >= min_n and second[0] >= min_n:
            pairs.append(((first[1] - first[2]) / first[0], (second[1] - second[2]) / second[0]))
    result = correlate(pairs, rng)
    if result:
        r = result["r"]
        result["spearman_brown"] = 2 * r / (1 + r) if r > -1 else None
    return result


def predictive(rows, probabilities, earlier, rng, permutations=PERMUTATIONS):
    """Does an earlier-period score improve the calibrated forecast of later big matches?
    Returns beta, its se, the log-loss change per match, and a permutation p-value."""
    big = [(r, p) for r, p in zip(rows, probabilities) if r["kind"] == "big"]
    if not big:
        return None
    offset = logit([p for _, p in big])
    y = np.array([r["y"] for r, _ in big])
    a = [r["a"] for r, _ in big]
    b = [r["b"] for r, _ in big]

    def fit(score_of):
        x = np.array([score_of.get(pa, 0.0) - score_of.get(pb, 0.0) for pa, pb in zip(a, b)])
        if not np.any(x):
            return 0.0, math.inf, 0.0
        beta, se = fit_one(x, y, offset)
        p0, p1 = sigmoid(offset), sigmoid(offset + beta * x)
        loss = lambda p: -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
        return beta, se, float(loss(p1) - loss(p0))

    beta, se, change = fit(earlier)
    players, values = list(earlier), np.array(list(earlier.values()))
    as_large = 0
    for _ in range(permutations):
        shuffled = dict(zip(players, rng.permutation(values)))
        if fit(shuffled)[2] <= change:
            as_large += 1
    with_history = sum(1 for pa, pb in zip(a, b) if pa in earlier or pb in earlier)
    return {"matches": len(big), "with_history": with_history, "beta": beta, "se": se,
            "log_loss_change": change, "permutation_p": (as_large + 1) / (permutations + 1)}


# ---------------------------------------------------------------- report

def pp(value):
    return f"{100 * value:+.1f}"


def resolve_named(matches):
    """{(tour, name): player id}, taking the id with most matches if a name has several."""
    counts = defaultdict(int)
    for match in matches:
        for side in ("winner", "loser"):
            counts[(match["tour"], match[f"{side}_name"], match[f"{side}_id"])] += 1
    found = {}
    for tour, name in NAMED:
        options = [(n, pid) for (t, nm, pid), n in counts.items() if t == tour and nm == name]
        if options:
            found[(tour, name)] = max(options)[1]
    return found


def main():
    out = Output()
    rng = np.random.default_rng(SEED)
    matches = load_matches()
    rows = match_rows(matches)
    summary = {"definitions": {"shrink": SHRINK, "min_big": MIN_BIG, "window": WINDOW, "period_1": PERIOD_1,
                               "period_2": PERIOD_2, "seed": SEED}}

    out("POST-HOC: is big-match performance a stable player trait? (descriptive, not pre-registered)")
    out("Baseline: canonical surface-blended Elo, recalibrated per (tour, big/regular, best-of) in each window.")
    out(f"Shrinkage: residual sum / (matches + {SHRINK}). Minimum {MIN_BIG} big matches where a minimum applies.")
    out()

    window_rows = within(rows, WINDOW)
    window_p, slopes = calibrate(window_rows)
    out(f"Window 2000 - May 2026: {len(window_rows):,} main-tour matches, "
        f"{sum(r['kind'] == 'big' for r in window_rows):,} of them big.")
    out("Elo log-odds calibration slopes (1.00 = Elo already right; above 1 = Elo too cautious):")
    for group in sorted(slopes, key=lambda g: (g[0], g[1], g[2])):
        out(f"   {group[0]} {group[1]:<8} best of {group[2]}: {slopes[group]:.2f}")
    summary["calibration_slopes"] = {f"{g[0]} {g[1]} bo{g[2]}": s for g, s in slopes.items()}
    out()

    out("1. SPREAD: how much do players' big-match results vary beyond coin-flip noise? (2000 - May 2026)")
    out("   Raw mean residual per match, in win-probability points. ratio = observed variance / noise variance;")
    out("   1.0 means the differences between players are what luck alone would produce.")
    out(f"   {'tour':<4} {'set':<22} {'players':>7} {'observed sd':>12} {'noise sd':>9} {'ratio':>6} "
        f"{'trait sd':>9} {'implied k':>10}")
    summary["spread"] = {}
    definitions = (("finals only", "big", {"F"}), ("semi-finals + finals", "big", {"SF", "F"}),
                   ("all big matches", "big", None), ("regular matches", "regular", None))
    for tour in ("ATP", "WTA"):
        tour_rows = [(r, p) for r, p in zip(window_rows, window_p) if r["tour"] == tour]
        for label, kind, rounds in definitions:
            stats = player_stats([r for r, _ in tour_rows], [p for _, p in tour_rows], kind, rounds)
            result = spread(stats)
            summary["spread"][f"{tour} {label}"] = result
            if result:
                implied = "none" if math.isinf(result["implied_k"]) else f"{result['implied_k']:.0f}"
                out(f"   {tour:<4} {label:<22} {result['players']:>7} {pp(result['observed_sd']):>12} "
                    f"{pp(result['noise_sd']):>9} {result['ratio']:>6.2f} {pp(result['trait_sd']):>9} {implied:>10}")
    out("   implied k = the shrinkage the data itself supports (matches needed before half the signal is real).")
    out()

    out("2. SPLIT-HALF: do a player's big matches in odd-numbered editions agree with the even ones? (2000 - May 2026)")
    summary["split_half"] = {}
    for tour in ("ATP", "WTA"):
        tour_rows = [(r, p) for r, p in zip(window_rows, window_p) if r["tour"] == tour]
        result = split_half([r for r, _ in tour_rows], [p for _, p in tour_rows], rng)
        summary["split_half"][tour] = result
        if result:
            out(f"   {tour}: {result['players']} players, r = {result['r']:+.3f} (95% {result['low']:+.3f} to "
                f"{result['high']:+.3f}); full-data reliability (Spearman-Brown) {result['spearman_brown']:+.3f}")
    out()

    out("3. PERIOD SPLIT: do 2012-2018 scores carry into 2019 - May 2026?")
    rows_1, rows_2 = within(rows, PERIOD_1), within(rows, PERIOD_2)
    p_1, _ = calibrate(rows_1)
    p_2, _ = calibrate(rows_2)
    summary["period_split"] = {}
    for tour in ("ATP", "WTA"):
        t1 = [(r, p) for r, p in zip(rows_1, p_1) if r["tour"] == tour]
        t2 = [(r, p) for r, p in zip(rows_2, p_2) if r["tour"] == tour]
        big_1 = player_stats([r for r, _ in t1], [p for _, p in t1], "big")
        reg_1 = player_stats([r for r, _ in t1], [p for _, p in t1], "regular")
        big_2 = player_stats([r for r, _ in t2], [p for _, p in t2], "big")
        reg_2 = player_stats([r for r, _ in t2], [p for _, p in t2], "regular")
        score_1, clutch_1 = scores(big_1, reg_1)
        score_2, clutch_2 = scores(big_2, reg_2)
        both = [pl for pl in score_1 if pl in score_2 and big_1[pl][0] >= MIN_BIG and big_2[pl][0] >= MIN_BIG]
        result = {}
        for label, first, second in (("big-match score", score_1, score_2), ("clutch score", clutch_1, clutch_2),
                                     ("regular-match score", {p: shrunk(reg_1.get(p)) for p in score_1},
                                      {p: shrunk(reg_2.get(p)) for p in score_2})):
            result[label] = correlate([(first[pl], second[pl]) for pl in both], rng)
        out(f"   {tour}: {len(both)} players with {MIN_BIG}+ big matches in both periods")
        for label, value in result.items():
            if value:
                out(f"      correlation of {label:<20} r = {value['r']:+.3f} (95% {value['low']:+.3f} to "
                    f"{value['high']:+.3f})")
        for label, earlier in (("big-match score", score_1), ("clutch score", clutch_1)):
            found = predictive([r for r, _ in t2], [p for _, p in t2], earlier, rng)
            result[f"forecast with {label}"] = found
            out(f"      forecast of {found['matches']:,} later big matches ({found['with_history']:,} with a "
                f"2012-2018 score) using the {label}: beta {found['beta']:+.2f} (se {found['se']:.2f}), "
                f"log loss change {found['log_loss_change']:+.5f} per match, permutation p = "
                f"{found['permutation_p']:.3f}")
        summary["period_split"][tour] = result
    out("   (The regular-match row is a reference: how much any Elo residual persists, pressure or not.)")
    out()

    out("NAMED PLAYERS: big matches, actual wins against calibrated-Elo expected wins")
    out("   score = shrunk residual per match in points; 95% = raw residual per match +/- 1.96 se.")
    named = resolve_named(matches)
    periods = (("2012-2018", rows_1, p_1), ("2019-May 2026", rows_2, p_2), ("2000-May 2026", window_rows, window_p))
    period_stats = {}
    for label, period_rows, period_p in periods:
        period_stats[label] = {
            "big": player_stats(period_rows, period_p, "big"),
            "final": player_stats(period_rows, period_p, "big", {"F"}),
            "regular": player_stats(period_rows, period_p, "regular"),
        }
    summary["named"] = {}
    out(f"   {'player':<20} {'period':<14} {'big':>4} {'won':>4} {'exp':>6} {'score':>6} {'raw 95%':>16} "
        f"{'finals won/exp':>15} {'clutch':>7}")
    for (tour, name), pid in named.items():
        key = (tour, pid)
        for label, _, _ in periods:
            stats = period_stats[label]
            big = stats["big"].get(key)
            if not big or big[0] == 0:
                continue
            final = stats["final"].get(key) or [0, 0, 0.0, 0.0]
            raw = (big[1] - big[2]) / big[0]
            half = 1.96 * math.sqrt(big[3]) / big[0]
            clutch = shrunk(big) - shrunk(stats["regular"].get(key))
            summary["named"][f"{name} {label}"] = {"big": big[0], "won": big[1], "expected": big[2],
                                                    "score": shrunk(big), "clutch": clutch,
                                                    "finals": final[0], "finals_won": final[1],
                                                    "finals_expected": final[2]}
            out(f"   {name:<20} {label:<14} {big[0]:>4} {big[1]:>4.0f} {big[2]:>6.1f} {pp(shrunk(big)):>6} "
                f"{pp(raw - half):>7} to {pp(raw + half):>5} {final[1]:>6.0f} / {final[2]:>5.1f} {pp(clutch):>7}")
    out()

    out("LARGEST SHRUNK BIG-MATCH SCORES, 2000 - May 2026 (players with 30+ big matches)")
    names = {}
    for match in matches:
        for side in ("winner", "loser"):
            names[(match["tour"], match[f"{side}_id"])] = match[f"{side}_name"]
    for tour in ("ATP", "WTA"):
        stats = period_stats["2000-May 2026"]
        eligible = [(shrunk(e), pl, e) for pl, e in stats["big"].items() if pl[0] == tour and e[0] >= 30]
        eligible.sort()
        for heading, chosen in (("top", eligible[::-1][:8]), ("bottom", eligible[:8])):
            out(f"   {tour} {heading}: " + "; ".join(
                f"{names[pl]} {pp(score)} ({e[1]:.0f}/{e[2]:.1f} of {e[0]})" for score, pl, e in chosen))
    out()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Saved {OUTPUT} and {SUMMARY}")


if __name__ == "__main__":
    main()

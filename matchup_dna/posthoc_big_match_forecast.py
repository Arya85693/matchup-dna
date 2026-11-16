"""POST-HOC, working paper 1 version 3: Elo calibration in big matches, and a chronological out-of-sample test of
player-specific big-match adjustments.

    python -m matchup_dna.posthoc_big_match_forecast

Written on 16 November 2026, after versions 1 and 2 of the paper and their results were known, in answer to an
audit. Nothing here changes a model, a frozen protocol or the live forecasts, and nothing reads data from June 2026
on: the matches, big-match definitions and window are matchup_dna.posthoc_big_match's (version 3 corrections).

Part 1, calibration. Elo's log-odds are rescaled by one slope per (tour, big or regular, best of). Is the big-match
slope different from the regular one? Model-based (Wald) standard errors treat matches as independent, so the
difference is also given a cluster bootstrap over tournament editions (every match of a resampled edition comes along),
and the slopes are refitted in three periods to see whether the difference is stable.

Part 2, out-of-sample forecasts. Version 1's "forecast test" fitted its coefficient on the same 2019-2026 matches it
scored, with calibrations fitted inside each period, so it is a retrospective association test. Here every forecast
uses only matches from earlier calendar years:

- For each year t (2004 to 2026), the calibration slopes are fitted on all matches from 2000 to the end of t - 1.
- Player scores at the start of t use residuals of matches from 2000 to t - 1 under that calibration: the version 1
  big-match score (residual sum / (n + 20)) and clutch score (big minus regular), plus two variants: empirical Bayes
  scores (normal-normal shrinkage with the trait variance estimated by method of moments from players with 10 or more
  matches before t) and recent scores (only the previous RECENT_YEARS years).
- The coefficient beta for evaluation year Y is fitted, per tour, on the big matches of 2004 to Y - 1, each with the
  calibration and scores of its own year. So beta, calibration and scores for a match in Y never see Y.
- Evaluation: every big match from 2012 to 24 May 2026. All models are scored on the same matches. A player with no
  earlier big matches has score 0, so no match is dropped.

Models: M0 Elo with one calibration slope per (tour, best of); M1 separate big and regular slopes (the study's
baseline); M2/M3 = M1 + beta x (big-match / clutch score difference), with EB and recent variants. Differences in log
loss and Brier score are paired by match; 95% intervals come from a cluster bootstrap over tournament editions.
"""
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from matchup_dna import posthoc_big_match as v1
from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import Output
from matchup_dna.load import DATA_DIR, load_matches, match_files

OUTPUT = RESULTS_DIR / "phase4" / "experiments" / "posthoc_big_match_forecast.txt"
SUMMARY = RESULTS_DIR / "phase4" / "experiments" / "posthoc_big_match_forecast.json"

TOURS = ("ATP", "WTA")
FIRST_FIT_YEAR = 2004            # first year whose matches can train beta (scores need 2000-2003 history)
FIRST_EVAL_YEAR = 2012
RECENT_YEARS = 5
MIN_EB = v1.MIN_BIG
BOOTSTRAPS = 2000
SEED = 20261116
PERIODS = ((2000, 2008), (2009, 2017), (2018, 2026))
SCORES = ("big", "clutch", "big_eb", "clutch_eb", "big_recent", "clutch_recent")
MODEL_NAMES = {
    "M0": "Elo, one calibration slope per tour and format",
    "M1": "Elo, separate big- and regular-match slopes (baseline)",
    "big": "M1 + big-match score (fixed shrinkage, k = 20)",
    "clutch": "M1 + clutch score (fixed shrinkage, k = 20)",
    "big_eb": "M1 + big-match score (empirical Bayes)",
    "clutch_eb": "M1 + clutch score (empirical Bayes)",
    "big_recent": f"M1 + big-match score, last {RECENT_YEARS} years only",
    "clutch_recent": f"M1 + clutch score, last {RECENT_YEARS} years only",
}

sigmoid, logit = v1.sigmoid, v1.logit


# ---------------------------------------------------------------- data

def arrays(rows):
    players, editions = {}, {}
    d = {
        "tour": np.array([r["tour"] for r in rows]),
        "year": np.array([r["date"] // 10000 for r in rows]),
        "big": np.array([r["kind"] == "big" for r in rows]),
        "bo5": np.array([r["best_of"] == 5 for r in rows]),
        "z": logit([r["p_a"] for r in rows]),
        "y": np.array([r["y"] for r in rows]),
        "a": np.array([players.setdefault(r["a"], len(players)) for r in rows]),
        "b": np.array([players.setdefault(r["b"], len(players)) for r in rows]),
        "edition": np.array([editions.setdefault((r["tour"], r["tourney_id"]), len(editions)) for r in rows]),
    }
    d["players"], d["editions"] = len(players), len(editions)
    return d


def groups(d, separate=True):
    """Calibration group: (tour, big or regular, best of) or, pooled, (tour, best of)."""
    return (d["tour"] == "WTA") * 4 + (d["big"] * 2 if separate else 0) + d["bo5"]


# ---------------------------------------------------------------- fitting

def fit_slope(z, y, w=None, offset=None, iterations=30):
    """Weighted maximum likelihood for logit P = offset + c z. Returns (c, model se)."""
    w = np.ones(len(z)) if w is None else w
    offset = np.zeros(len(z)) if offset is None else offset
    c = 1.0 if offset is None or not np.any(offset) else 0.0
    for _ in range(iterations):
        p = sigmoid(offset + c * z)
        grad, info = np.sum(w * (y - p) * z), np.sum(w * p * (1 - p) * z * z)
        if info <= 0:
            break
        step = grad / info
        c += step
        if abs(step) < 1e-10:
            break
    p = sigmoid(offset + c * z)
    info = np.sum(w * p * (1 - p) * z * z)
    return float(c), (1 / math.sqrt(info) if info > 0 else math.inf)


def calibrated(d, train, apply, separate=True):
    """Probabilities for rows in `apply` from slopes fitted on rows in `train`, one slope per group."""
    g = groups(d, separate)
    p = np.full(len(g), np.nan)
    for group in np.unique(g[apply]):
        fit = train & (g == group)
        slope, _ = fit_slope(d["z"][fit], d["y"][fit])
        chosen = apply & (g == group)
        p[chosen] = sigmoid(slope * d["z"][chosen])
    return p


# ---------------------------------------------------------------- part 1: calibration

def slope_difference(d, mask, rng, reps=BOOTSTRAPS):
    """Big minus regular slope for each (tour, best of) inside `mask`, with Wald and edition-cluster bootstrap
    uncertainty."""
    out = {}
    for tour in TOURS:
        for bo5 in (False, True):
            base = mask & (d["tour"] == tour) & (d["bo5"] == bo5)
            if not np.any(base & d["big"]):
                continue
            big, reg = base & d["big"], base & ~d["big"]
            sb, seb = fit_slope(d["z"][big], d["y"][big])
            sr, ser = fit_slope(d["z"][reg], d["y"][reg])
            entry = {"big": sb, "big_se": seb, "big_n": int(big.sum()), "regular": sr, "regular_se": ser,
                     "regular_n": int(reg.sum()), "difference": sb - sr}
            entry["wald_z"] = entry["difference"] / math.hypot(seb, ser)
            entry["wald_p"] = math.erfc(abs(entry["wald_z"]) / math.sqrt(2))
            if reps:
                eds = d["edition"][base]
                unique, local = np.unique(eds, return_inverse=True)
                draws = []
                zb, yb, lb = d["z"][big], d["y"][big], local[d["big"][base]]
                zr, yr, lr = d["z"][reg], d["y"][reg], local[~d["big"][base]]
                for _ in range(reps):
                    weight = np.bincount(rng.integers(0, len(unique), len(unique)), minlength=len(unique)).astype(float)
                    draws.append(fit_slope(zb, yb, weight[lb])[0] - fit_slope(zr, yr, weight[lr])[0])
                draws = np.array(draws)
                se = float(np.std(draws, ddof=1))
                entry.update({"cluster_se": se, "cluster_z": entry["difference"] / se,
                              "cluster_p": math.erfc(abs(entry["difference"] / se) / math.sqrt(2)),
                              "cluster_low": float(np.percentile(draws, 2.5)),
                              "cluster_high": float(np.percentile(draws, 97.5)), "editions": int(len(unique))})
            out[f"{tour} bo{5 if bo5 else 3}"] = entry
    return out


# ---------------------------------------------------------------- part 2: scores and forecasts

def player_totals(d, residual, variance, mask):
    size, a, b = d["players"], d["a"][mask], d["b"][mask]
    n = (np.bincount(a, minlength=size) + np.bincount(b, minlength=size)).astype(float)
    s = np.bincount(a, residual[mask], size) - np.bincount(b, residual[mask], size)
    v = np.bincount(a, variance[mask], size) + np.bincount(b, variance[mask], size)
    return n, s, v


def eb_shrink(mean, noise, eligible):
    """Normal-normal posterior mean of a zero-centred trait: mean x tau2 / (tau2 + noise), with tau2 = method-of-
    moments trait variance over eligible players (observed variance of means minus average noise, floored at 0)."""
    if eligible.sum() < 3:
        return np.zeros(len(mean)), 0.0
    tau2 = max(0.0, float(np.mean(mean[eligible] ** 2) - np.mean(noise[eligible])))
    out = np.where(np.isfinite(noise) & (noise > 0), mean * tau2 / (tau2 + noise), 0.0)
    return out, tau2


def scores_at(d, year, tour_mask, p_hist, history):
    """Scores of every player from residuals of matches in `history` (all before `year`) under p_hist."""
    residual, variance = d["y"] - p_hist, p_hist * (1 - p_hist)
    found, tau2 = {}, {}
    for label, mask in (("", history), ("_recent", history & (d["year"] >= year - RECENT_YEARS))):
        nb, sb, vb = player_totals(d, residual, variance, tour_mask & mask & d["big"])
        nr, sr, vr = player_totals(d, residual, variance, tour_mask & mask & ~d["big"])
        big = sb / (nb + v1.SHRINK)
        found["big" + label] = big
        found["clutch" + label] = np.where(nb > 0, big - sr / (nr + v1.SHRINK), 0.0)
        if label == "":
            with np.errstate(divide="ignore", invalid="ignore"):
                mean_b, noise_b = np.where(nb > 0, sb / nb, 0.0), np.where(nb > 0, vb / nb ** 2, np.inf)
                diff = np.where((nb > 0) & (nr > 0), sb / np.maximum(nb, 1) - sr / np.maximum(nr, 1), 0.0)
                noise_d = np.where((nb > 0) & (nr > 0), vb / np.maximum(nb, 1) ** 2 + vr / np.maximum(nr, 1) ** 2, np.inf)
            found["big_eb"], tau2["big"] = eb_shrink(mean_b, noise_b, nb >= MIN_EB)
            found["clutch_eb"], tau2["clutch"] = eb_shrink(diff, noise_d, (nb >= MIN_EB) & (nr >= MIN_EB))
            found["_n_big"] = nb
    return found, tau2


def chronological(d):
    """Per year t: baseline probabilities (M0, M1) for t's matches and score differences, all from data before t."""
    per_year, eb_tau = {}, {}
    for t in range(FIRST_FIT_YEAR, int(d["year"].max()) + 1):
        history, current = d["year"] < t, d["year"] == t
        if not np.any(current):
            continue
        m0 = calibrated(d, history, current, separate=False)
        m1 = calibrated(d, history, current, separate=True)
        p_hist = calibrated(d, history, history, separate=True)
        x = {key: np.full(len(d["y"]), np.nan) for key in SCORES}
        known = np.zeros(len(d["y"]), dtype=bool)
        eb_tau[t] = {}
        for tour in TOURS:
            tour_mask = d["tour"] == tour
            found, tau2 = scores_at(d, t, tour_mask, p_hist, history)
            eb_tau[t][tour] = tau2
            rows = current & tour_mask
            for key in SCORES:
                x[key][rows] = found[key][d["a"][rows]] - found[key][d["b"][rows]]
            known[rows] = (found["_n_big"][d["a"][rows]] >= v1.MIN_BIG) & (found["_n_big"][d["b"][rows]] >= v1.MIN_BIG)
        per_year[t] = {"m0": m0, "m1": m1, "x": x, "known": known}
    return per_year, eb_tau


def evaluate(d, per_year):
    """Out-of-sample probabilities for every match of the evaluation years, and the beta used each year."""
    n = len(d["y"])
    prob = {name: np.full(n, np.nan) for name in ("M0", "M1", *SCORES)}
    known = np.zeros(n, dtype=bool)
    betas = {key: {tour: {} for tour in TOURS} for key in SCORES}
    years = sorted(per_year)
    for year in (y for y in years if y >= FIRST_EVAL_YEAR):
        rows = d["year"] == year
        prob["M0"][rows], prob["M1"][rows] = per_year[year]["m0"][rows], per_year[year]["m1"][rows]
        known |= rows & per_year[year]["known"]
        for tour in TOURS:
            target = rows & (d["tour"] == tour) & d["big"]
            train = [t for t in years if t < year]
            for key in SCORES:
                xs, ys, offs = [], [], []
                for t in train:
                    m = (d["year"] == t) & (d["tour"] == tour) & d["big"]
                    xs.append(per_year[t]["x"][key][m]); ys.append(d["y"][m]); offs.append(logit(per_year[t]["m1"][m]))
                xs, ys, offs = np.concatenate(xs), np.concatenate(ys), np.concatenate(offs)
                beta = fit_slope(xs, ys, offset=offs)[0] if np.any(xs) else 0.0
                betas[key][tour][year] = beta
                prob[key][target] = sigmoid(logit(per_year[year]["m1"][target]) + beta * per_year[year]["x"][key][target])
    return prob, known, betas


def losses(p, y):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p)), (p - y) ** 2


def compare(d, prob, rows, reference, rng, reps=BOOTSTRAPS):
    """Mean log loss and Brier for each model on `rows`, and paired differences from `reference` with a cluster
    bootstrap over tournament editions."""
    y = d["y"][rows]
    eds, local = np.unique(d["edition"][rows], return_inverse=True)
    weights = [np.bincount(rng.integers(0, len(eds), len(eds)), minlength=len(eds)).astype(float) for _ in range(reps)]
    counts = np.bincount(local, minlength=len(eds)).astype(float)
    ref_ll, ref_br = losses(prob[reference][rows], y)
    out = {"matches": int(rows.sum()), "editions": int(len(eds)), "models": {}}
    for name, p in prob.items():
        if np.isnan(p[rows]).any():
            continue
        ll, br = losses(p[rows], y)
        entry = {"log_loss": float(ll.mean()), "brier": float(br.mean())}
        if name != reference:
            for metric, diff in (("log_loss", ll - ref_ll), ("brier", br - ref_br)):
                sums = np.bincount(local, diff, len(eds))
                draws = np.array([w @ sums / (w @ counts) for w in weights])
                entry[f"{metric}_diff"] = float(diff.mean())
                entry[f"{metric}_low"], entry[f"{metric}_high"] = (float(x) for x in np.percentile(draws, [2.5, 97.5]))
                entry[f"{metric}_share_better"] = float(np.mean(draws < 0))
        out["models"][name] = entry
    return out


# ---------------------------------------------------------------- provenance

def manifest():
    files = []
    for tour in TOURS:
        for path in match_files(tour):
            year = int(path.stem[-4:])
            if 1968 <= year <= 2026:
                files.append({"file": path.relative_to(DATA_DIR).as_posix(),
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    analysis = ["matchup_dna/posthoc_big_match.py", "matchup_dna/posthoc_big_match_robustness.py",
                "matchup_dna/posthoc_big_match_players.py", "matchup_dna/posthoc_big_match_forecast.py"]
    try:
        root = DATA_DIR.parent
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=root).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", *analysis], capture_output=True, text=True,
                               cwd=root).stdout.strip()
    except OSError:
        commit, dirty = None, None
    return {"data_files": files, "code_commit_at_run": commit,
            "analysis_code_committed": None if dirty is None else dirty == ""}


# ---------------------------------------------------------------- report

def main():
    out = Output()
    rng = np.random.default_rng(SEED)
    rows = v1.within(v1.match_rows(load_matches()), v1.WINDOW)
    d = arrays(rows)
    summary = {"definitions": {"window": v1.WINDOW, "first_fit_year": FIRST_FIT_YEAR, "first_eval_year": FIRST_EVAL_YEAR,
                               "recent_years": RECENT_YEARS, "bootstraps": BOOTSTRAPS, "seed": SEED, "shrink": v1.SHRINK,
                               "min_big": v1.MIN_BIG, "periods": PERIODS, "models": MODEL_NAMES},
               "provenance": manifest()}
    out("POST-HOC (version 3): calibration in big matches, and an out-of-sample test of player big-match adjustments")
    out(f"{len(d['y']):,} matches ({int(d['big'].sum()):,} big), {d['editions']:,} tournament editions, {v1.WINDOW}.")
    out()

    out("1. CALIBRATION SLOPES, big against regular (model-based Wald test and edition-cluster bootstrap)")
    full = slope_difference(d, np.ones(len(d["y"]), dtype=bool), rng)
    summary["calibration"] = {"window": full, "periods": {}}
    for key, e in full.items():
        out(f"   {key}: big {e['big']:.3f} (se {e['big_se']:.3f}) regular {e['regular']:.3f} (se {e['regular_se']:.3f}); "
            f"difference {e['difference']:+.3f}; Wald p {e['wald_p']:.4f}; cluster se {e['cluster_se']:.3f}, "
            f"p {e['cluster_p']:.4f}, 95% {e['cluster_low']:+.3f} to {e['cluster_high']:+.3f} ({e['editions']:,} editions)")
    for start, end in PERIODS:
        mask = (d["year"] >= start) & (d["year"] <= end)
        found = slope_difference(d, mask, rng, reps=0)
        summary["calibration"]["periods"][f"{start}-{end}"] = found
        out(f"   {start}-{end}: " + "; ".join(f"{k} {e['big']:.2f} vs {e['regular']:.2f} (diff {e['difference']:+.3f}, "
                                              f"Wald p {e['wald_p']:.3f})" for k, e in found.items()))
    out()

    out(f"2. OUT-OF-SAMPLE FORECASTS: every big match {FIRST_EVAL_YEAR} - May 2026, each year predicted only from earlier years")
    per_year, eb_tau = chronological(d)
    prob, known, betas = evaluate(d, per_year)
    summary["eb_trait_variance"] = {str(t): v for t, v in eb_tau.items()}
    summary["betas"] = {k: {tour: {str(y): b for y, b in v.items()} for tour, v in t.items()} for k, t in betas.items()}
    eval_rows = d["year"] >= FIRST_EVAL_YEAR
    summary["forecast"] = {}
    for label, rows_mask in (("big matches", eval_rows & d["big"]), ("big matches, both players with 10+ earlier big",
                                                                       eval_rows & d["big"] & known)):
        for tour in (*TOURS, "both"):
            mask = rows_mask & (True if tour == "both" else d["tour"] == tour)
            found = compare(d, prob, mask, "M1", rng)
            summary["forecast"][f"{tour}|{label}"] = found
            out(f"   {tour}, {label}: {found['matches']:,} matches, {found['editions']:,} editions")
            for name, e in found["models"].items():
                extra = "" if name == "M1" else (
                    f"  vs M1: log loss {e['log_loss_diff']:+.5f} (95% {e['log_loss_low']:+.5f} to {e['log_loss_high']:+.5f}), "
                    f"Brier {e['brier_diff']:+.5f} (95% {e['brier_low']:+.5f} to {e['brier_high']:+.5f})")
                out(f"      {name:<14} log loss {e['log_loss']:.5f}  Brier {e['brier']:.5f}{extra}")
    # Tour-level calibration on all matches (does the big/regular split help unseen regular matches too?).
    for tour in TOURS:
        mask = eval_rows & (d["tour"] == tour)
        found = compare(d, {"M0": prob["M0"], "M1": prob["M1"]}, mask, "M0", rng)
        summary["forecast"][f"{tour}|all matches"] = found
        e = found["models"]["M1"]
        out(f"   {tour}, all matches ({found['matches']:,}): M1 vs M0 log loss {e['log_loss_diff']:+.5f} "
            f"(95% {e['log_loss_low']:+.5f} to {e['log_loss_high']:+.5f})")
    # Year by year, both tours, big matches: M1 vs M0 and the two primary scores vs M1.
    summary["by_year"] = {}
    for year in range(FIRST_EVAL_YEAR, int(d["year"].max()) + 1):
        mask = (d["year"] == year) & d["big"]
        y = d["y"][mask]
        ref = losses(prob["M1"][mask], y)[0]
        summary["by_year"][str(year)] = {"matches": int(mask.sum()), **{
            name: float((losses(prob[name][mask], y)[0] - ref).mean()) for name in ("M0", "big", "clutch")}}
    out("   by year, big matches, mean log-loss difference vs M1 (M0, big, clutch): " + "; ".join(
        f"{y} {v['M0']:+.4f} {v['big']:+.4f} {v['clutch']:+.4f}" for y, v in summary["by_year"].items()))
    out("   beta by evaluation year (big / clutch, k = 20): " + "; ".join(
        f"{tour} " + ", ".join(f"{y}: {betas['big'][tour][y]:+.2f}/{betas['clutch'][tour][y]:+.2f}" for y in sorted(betas['big'][tour]))
        for tour in TOURS))
    out()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Saved {OUTPUT} and {SUMMARY}")


if __name__ == "__main__":
    main()

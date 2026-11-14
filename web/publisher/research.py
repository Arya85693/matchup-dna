"""The historical research figures the website shows (Phases 2-5), exported once from the saved results.

    python -m web.publisher.research          writes web/content/research/{historical,market,big-match}.json

Run by hand when the research changes, not on the twice-daily schedule. Every headline number is either recomputed from
a saved prediction file or read from a saved results file, and then **asserted equal to the value printed in the
published report** (to the report's precision). A mismatch stops the export. Each output names its source files and
their sha256, so the figures are traceable. Only aggregates leave: no match-level rows, no player data, no prices.

Phase 2 has no machine-readable result file; its figures are copied from the report with their line references.
"""
import csv
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
OUT = ROOT / "web" / "content" / "research"
BINS = 10


class Mismatch(AssertionError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(value, published, places, what):
    """value must round to the printed figure."""
    if round(value, places) != round(published, places):
        raise Mismatch(f"{what}: computed {value!r}, the report prints {published}")
    return value


def scores(p, y):
    n = len(p)
    ll = -sum(math.log(q) if t else math.log(1 - q) for q, t in zip(p, y)) / n
    brier = sum((q - t) ** 2 for q, t in zip(p, y)) / n
    acc = sum(0.5 if q == 0.5 else float((q > 0.5) == bool(t)) for q, t in zip(p, y)) / n
    return {"n": n, "log_loss": ll, "brier": brier, "accuracy": acc}


def reliability(p, y, bins=BINS):
    """Ten equal-width bins of the forecast probability, as prospective.reliability, with a 95% Wilson interval."""
    found = []
    for b in range(bins):
        low, high = b / bins, (b + 1) / bins
        idx = [i for i, q in enumerate(p) if low <= q < high or (b == bins - 1 and q == 1.0)]
        if not idx:
            continue
        n = len(idx)
        obs = sum(y[i] for i in idx) / n
        z = 1.96
        centre = (obs + z * z / (2 * n)) / (1 + z * z / n)
        half = z * math.sqrt(obs * (1 - obs) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        found.append({"low": low, "high": high, "n": n, "mean_p": sum(p[i] for i in idx) / n, "observed": obs,
                      "observed_low": centre - half, "observed_high": centre + half})
    return found


def read(path, column):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows, [float(r[column]) for r in rows], [int(r["a_won"]) for r in rows]


def phase3():
    path = RESULTS / "phase3" / "final" / "reserved_predictions.csv"
    rows, p, y = read(path, "Selected model")
    _, elo, _ = read(path, "Surface Elo, temperature")
    model, base = scores(p, y), scores(elo, y)
    # docs/Phase 3 - Model Report.md, lines 240-241: combined 0.6128 / 0.6207, Brier 0.2128, accuracy 65.58%, n 13,732
    same(model["n"], 13732, 0, "Phase 3 reserved matches")
    same(model["log_loss"], 0.6128, 4, "Phase 3 selected model log loss")
    same(base["log_loss"], 0.6207, 4, "Phase 3 calibrated surface Elo log loss")
    same(model["brier"], 0.2128, 4, "Phase 3 Brier")
    same(model["accuracy"], 0.6558, 4, "Phase 3 accuracy")
    by_tour = {t: scores([q for q, r in zip(p, rows) if r["tour"] == t], [v for v, r in zip(y, rows) if r["tour"] == t])
               for t in ("ATP", "WTA")}
    same(by_tour["ATP"]["log_loss"], 0.6116, 4, "Phase 3 ATP")
    same(by_tour["WTA"]["log_loss"], 0.6142, 4, "Phase 3 WTA")
    return {"model": model, "benchmark": base, "by_tour": by_tour, "reliability": reliability(p, y),
            "source": {"file": "results/phase3/final/reserved_predictions.csv", "sha256": sha(path)}}


def phase4():
    summary_path = RESULTS / "phase4" / "corrected" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    corrected_path = RESULTS / "phase4" / "corrected" / "heldout_predictions.csv"
    original_path = RESULTS / "phase4" / "final" / "heldout_predictions.csv"
    _, p_c, y_c = read(corrected_path, "P4-refit")
    _, p3_c, _ = read(corrected_path, "P3-refit")
    _, p_o, y_o = read(original_path, "P4-refit")
    corrected, original = scores(p_c, y_c), scores(p_o, y_o)
    # docs/Phase 4 - Matchup Intelligence Report.md, line 481: 0.6108 / 0.2121 / 65.47% (2,518 rows); 0.6065 / 0.2102 / 65.86%
    same(original["n"], 2518, 0, "Phase 4 original held-out rows")
    same(original["log_loss"], 0.6108, 4, "Phase 4 original log loss")
    same(corrected["n"], 2453, 0, "Phase 4 corrected matches")
    same(corrected["log_loss"], 0.6065, 4, "Phase 4 corrected log loss")
    same(corrected["accuracy"], 0.6586, 4, "Phase 4 corrected accuracy")
    gap_o, gap_c = summary["original"]["gaps"]["Both"], summary["corrected"]["gaps"]["Both"]
    same(gap_o["gap"], -0.0040, 4, "Phase 4 pre-registered gap")
    same(gap_o["p"], 0.055, 3, "Phase 4 pre-registered p")
    same(gap_c["gap"], -0.0049, 4, "Phase 4 corrected gap")
    ra_o, ra_c = summary["original"]["round_aware"], summary["corrected"]["round_aware"]
    same(ra_o["gap"], -0.0072, 4, "R0 pre-registered gap")
    same(ra_c["gap"], -0.0059, 4, "R0 corrected gap")
    keep = ("rows", "gap", "se", "low", "high", "p")
    long_path = RESULTS / "phase4" / "experiments" / "posthoc_longrun_predictions_corrected.csv"
    with open(long_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    by_year = defaultdict(lambda: ([], [], []))
    for r in rows:
        year = r["tourney_date"][:4]
        by_year[year][0].append(float(r["Phase 4"]))
        by_year[year][1].append(float(r["Elo"]))
        by_year[year][2].append(int(r["a_won"]))
    years = []
    for year in sorted(by_year):
        p4, elo, y = by_year[year]
        years.append({"year": int(year), "phase4": scores(p4, y), "elo": scores(elo, y)})
    return {
        "held_out_original": {"scores": original, "p3_gap": {k: gap_o[k] for k in keep}},
        "held_out_corrected": {"scores": corrected, "p3": scores(p3_c, y_c), "p3_gap": {k: gap_c[k] for k in keep},
                               "reliability": reliability(p_c, y_c)},
        "round_aware_original": {k: ra_o[k] for k in keep}, "round_aware_corrected": {k: ra_c[k] for k in keep},
        "long_run_by_year": years,
        "sources": [{"file": f"results/phase4/{p.relative_to(RESULTS / 'phase4').as_posix()}", "sha256": sha(p)}
                    for p in (summary_path, corrected_path, original_path, long_path)],
    }


def phase5():
    path = RESULTS / "phase5" / "evaluation" / "evaluation.json"
    text = path.read_text(encoding="utf-8").replace("NaN", "null")
    e = json.loads(text)["all"]
    s, g = e["scores"], e["gaps"]
    # docs/Phase 5 - Quantitative Research Report.md, lines 113-127 and 208
    same(s["opening market"]["log_loss"], 0.5896, 4, "market log loss")
    same(s["Phase 4"]["log_loss"], 0.6132, 4, "Phase 4 log loss against the market")
    same(s["opening market"]["matches"], 13846, 0, "market matches")
    same(g["Phase 4"]["gap"], 0.0236, 4, "Q1 gap")
    same(e["backtests"]["primary"]["roi"], -0.089, 3, "primary ROI")
    same(e["slopes"]["Phase 4"]["b"], -0.067, 3, "information slope")

    def clean(d):
        return {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in d.items()}
    return {
        "matches": s["opening market"]["matches"], "window": "January 2024 to October 2026",
        "scores": {k: clean({x: v[x] for x in ("matches", "log_loss", "brier", "accuracy")}) for k, v in s.items()},
        "gaps": {k: clean(v) for k, v in g.items()},
        "information_slope": clean(e["slopes"]["Phase 4"]),
        "by_year": {k: clean(v) for k, v in e["slices"]["year"].items() if (v.get("matches") or 0) >= 100},
        "by_tour": {k: clean(v) for k, v in e["slices"]["tour"].items()},
        "by_ranking": {k: clean(v) for k, v in e["slices"]["ranking"].items()},
        "closing": e["closing"],
        "backtests": {k: clean({x: v.get(x) for x in ("bets", "roi", "roi_interval", "hit_rate", "mean_odds",
                                                      "expected_roi_if_market_right", "share_beating_close",
                                                      "final_bankroll")}) for k, v in e["backtests"].items()},
        "source": {"file": "results/phase5/evaluation/evaluation.json", "sha256": sha(path)},
    }


PHASE2 = {  # Phase 2 - Elo Report.md, validation table lines 141-142 and difference line 149 (no result file exists)
    "window": "2021 to 2023 (validation years)",
    "ATP": {"n": 8366, "elo": 0.6277, "surface_elo": 0.6245, "accuracy_surface_elo": 0.6494},
    "WTA": {"n": 7673, "elo": 0.6186, "surface_elo": 0.6183, "accuracy_surface_elo": 0.6561},
    "source": {"file": "Phase 2 - Elo Report.md", "lines": "141-149"},
}


def losing_run(finals, p_win, run):
    """Exact probability of at least one run of `run` straight losses in `finals` independent finals."""
    state = [1.0] + [0.0] * (run - 1)          # probability of each current losing-run length
    for _ in range(finals):
        nxt = [0.0] * run
        for length, mass in enumerate(state):
            nxt[0] += mass * p_win
            if length + 1 < run:
                nxt[length + 1] += mass * (1 - p_win)
        state = nxt
    return 1 - sum(state)


def big_match():
    """The post-hoc myth check (docs/Myth Check - Do Players Choke in Big Matches.md). Aggregates only: the source
    file also holds a few named players' figures for the report's illustration, and none of them leave."""
    path = RESULTS / "phase4" / "experiments" / "posthoc_big_match.json"
    s = json.loads(path.read_text(encoding="utf-8"))
    finite = lambda v: v if isinstance(v, (int, float)) and math.isfinite(v) else None

    # Report, "Calibration slopes" table.
    slopes = s["calibration_slopes"]
    printed = {"ATP big bo3": 0.74, "ATP big bo5": 1.01, "ATP regular bo3": 0.75, "ATP regular bo5": 1.06,
               "WTA big bo3": 0.75, "WTA regular bo3": 0.82}
    calibration = []
    for key, value in printed.items():
        tour, kind, bo = key.split()
        calibration.append({"tour": tour, "kind": kind, "best_of": int(bo[2:]),
                            "slope": same(slopes[key], value, 2, f"calibration slope {key}")})

    # Report, test 1 table: players, ratio (and the sds in points, one decimal).
    printed = {("ATP", "finals only"): (108, 0.99), ("ATP", "semi-finals + finals"): (222, 1.04),
               ("ATP", "all big matches"): (247, 1.17), ("ATP", "regular matches"): (813, 1.03),
               ("WTA", "finals only"): (82, 1.15), ("WTA", "semi-finals + finals"): (223, 1.00),
               ("WTA", "all big matches"): (251, 0.92), ("WTA", "regular matches"): (794, 1.29)}
    spread = []
    for (tour, label), (players, ratio) in printed.items():
        row = s["spread"][f"{tour} {label}"]
        same(row["players"], players, 0, f"spread players {tour} {label}")
        same(row["ratio"], ratio, 2, f"spread ratio {tour} {label}")
        spread.append({"tour": tour, "set": label, "players": row["players"], "ratio": row["ratio"],
                       "observed_sd": row["observed_sd"], "noise_sd": row["noise_sd"], "trait_sd": row["trait_sd"],
                       "implied_k": finite(row["implied_k"])})

    # Report, test 2 table.
    printed = {"ATP": (149, 0.094, -0.051, 0.238), "WTA": (132, 0.064, -0.125, 0.245)}
    split_half = {}
    for tour, (players, r, low, high) in printed.items():
        row = s["split_half"][tour]
        same(row["players"], players, 0, f"split-half players {tour}")
        for key, value in (("r", r), ("low", low), ("high", high)):
            same(row[key], value, 3, f"split-half {key} {tour}")
        split_half[tour] = {k: row[k] for k in ("players", "r", "low", "high", "spearman_brown")}

    # Report, test 3 tables.
    printed = {
        "ATP": {"players": 29, "big-match score": (0.203, -0.182, 0.547), "clutch score": (0.095, -0.285, 0.421),
                "regular-match score": (0.236, -0.097, 0.540),
                "forecast with big-match score": (1.19, -0.00036, 0.250),
                "forecast with clutch score": (1.20, -0.00049, 0.164), "matches": 2013},
        "WTA": {"players": 32, "big-match score": (0.163, -0.126, 0.410), "clutch score": (0.072, -0.249, 0.377),
                "regular-match score": (0.419, 0.016, 0.644),
                "forecast with big-match score": (2.29, -0.00100, 0.114),
                "forecast with clutch score": (-0.03, -0.00000, 0.967), "matches": 1672},
    }
    period_split = {}
    for tour, want in printed.items():
        row = s["period_split"][tour]
        out = {"players": None, "correlations": {}, "forecasts": {}}
        for label in ("big-match score", "clutch score", "regular-match score"):
            c = row[label]
            same(c["players"], want["players"], 0, f"period players {tour}")
            for key, value in zip(("r", "low", "high"), want[label]):
                same(c[key], value, 3, f"period {label} {key} {tour}")
            out["players"] = c["players"]
            out["correlations"][label.removesuffix(" score")] = {k: c[k] for k in ("r", "low", "high")}
        for label in ("forecast with big-match score", "forecast with clutch score"):
            f = row[label]
            beta, change, p = want[label]
            same(f["matches"], want["matches"], 0, f"{label} matches {tour}")
            same(f["beta"], beta, 2, f"{label} beta {tour}")
            same(f["log_loss_change"], change, 5, f"{label} log loss change {tour}")
            same(f["permutation_p"], p, 3, f"{label} p {tour}")
            out["forecasts"][label.removeprefix("forecast with ").removesuffix(" score")] = {
                k: f[k] for k in ("matches", "with_history", "beta", "se", "log_loss_change", "permutation_p")}
        period_split[tour] = out

    # Report, "Why the story feels true": 98% and 71% for a 60% finals winner over 29 finals.
    streak = {"finals": 29, "p_win": 0.6,
              "two": same(losing_run(29, 0.6, 2), 0.98, 2, "two-final losing run"),
              "three": same(losing_run(29, 0.6, 3), 0.71, 2, "three-final losing run")}

    # Report, "Data and definitions": the window's match counts, read from the printed output.
    text_path = path.with_suffix(".txt")
    counts = re.search(r"Window 2000 - May 2026: ([\d,]+) main-tour matches, ([\d,]+) of them big", text_path.read_text(encoding="utf-8"))
    matches, big = (int(counts.group(i).replace(",", "")) for i in (1, 2))
    same(matches, 131649, 0, "window matches")
    same(big, 14071, 0, "window big matches")

    definitions = s["definitions"]
    return {
        "schema_version": "2", "evidence": "post-hoc", "robustness": big_match_robustness(),
        "window": "2000 – May 2026", "matches": matches, "big_matches": big,
        "shrink": definitions["shrink"], "min_big": definitions["min_big"],
        "periods": ["2012–2018", "2019 – May 2026"],
        "calibration": calibration, "spread": spread, "split_half": split_half, "period_split": period_split,
        "streak": streak,
        "sources": [{"file": f"results/phase4/experiments/{p.name}", "sha256": sha(p)} for p in (path, text_path)],
    }


ROBUSTNESS_TESTS = ("ratio finals only", "ratio semi-finals + finals", "ratio all big matches", "ratio regular matches",
                    "clutch ratio", "split-half r", "period r big", "period r clutch", "forecast z big", "forecast z clutch")
SETS = ("finals only", "semi-finals + finals", "all big matches", "regular matches")

# Version 2 report ("Robustness, power and sensitivity" in docs/Myth Check - Do Players Choke in Big Matches.md): the
# figures as printed there. Every one is asserted against the analysis output before anything is written.
PRINTED_V2 = {
    "slope_tests": {"ATP 3": (0.735, 0.748, -0.43, 0.67), "ATP 5": (1.005, 1.064, -1.02, 0.31),
                    "WTA 3": (0.748, 0.822, -2.74, 0.006)},
    "null_p": {
        "ATP": {"ratio finals only": 0.501, "ratio semi-finals + finals": 0.358, "ratio all big matches": 0.062,
                "ratio regular matches": 0.365, "clutch ratio": 0.044, "split-half r": 0.147, "period r big": 0.148,
                "period r clutch": 0.314, "forecast z big": 0.123, "forecast z clutch": 0.082},
        "WTA": {"ratio finals only": 0.172, "ratio semi-finals + finals": 0.462, "ratio all big matches": 0.760,
                "ratio regular matches": 0.000, "clutch ratio": 0.543, "split-half r": 0.245, "period r big": 0.193,
                "period r clutch": 0.340, "forecast z big": 0.033, "forecast z clutch": 0.498},
    },
    "clutch_ratio": {"ATP": 1.20, "WTA": 0.98},
    "holm": {"ATP all big matches": 0.437, "WTA regular matches": 0.004},
    "power_at_0.2": {"ATP": {"clutch ratio": 0.43, "split-half r": 0.61, "forecast z clutch": 0.42},
                     "WTA": {"clutch ratio": 0.42, "split-half r": 0.55, "forecast z clutch": 0.37}},
    "bounds": {"ATP": {"clutch ratio": 0.320, "split-half r": 0.247, "forecast z clutch": 0.392},
               "WTA": {"clutch ratio": 0.200, "split-half r": 0.241, "forecast z clutch": 0.279}},
}


def big_match_robustness():
    """Version 2 of the myth check: exact null tests, power and bounds, game margins, within-tournament ratings and
    sensitivity (matchup_dna.posthoc_big_match_robustness). Aggregates only."""
    path = RESULTS / "phase4" / "experiments" / "posthoc_big_match_robustness.json"
    s = json.loads(path.read_text(encoding="utf-8"))
    want = PRINTED_V2
    if not s["reproduction"]["checked"] or s["reproduction"]["largest_difference"] > 1e-9:
        raise Mismatch("the robustness run did not reproduce the version 1 point estimates")

    slope_tests = []
    for key, (big, regular, z, p) in want["slope_tests"].items():
        tour, bo = key.split()
        row = s["slope_tests"][f"{tour} bo{bo}"]
        same(row["big"], big, 3, f"slope big {key}")
        same(row["regular"], regular, 3, f"slope regular {key}")
        same(row["z"], z, 2, f"slope z {key}")
        same(row["p"], p, 3 if p < 0.01 else 2, f"slope p {key}")
        slope_tests.append({"tour": tour, "best_of": int(bo), **{k: row[k] for k in ("big", "big_se", "regular",
                                                                                    "regular_se", "z", "p")}})

    null = []
    for tour in ("ATP", "WTA"):
        found = s["null"][tour]
        for test in ROBUSTNESS_TESTS:
            same(found["p"][test], want["null_p"][tour][test], 3, f"null p {tour} {test}")
            null.append({"tour": tour, "test": test, "observed": found["observed"][test],
                         "critical": found["critical"][test], "p": found["p"][test]})
        same(found["clutch"]["ratio"], want["clutch_ratio"][tour], 2, f"clutch ratio {tour}")
    holm = []
    for key, value in s["holm"].items():
        if key in want["holm"]:
            same(value, want["holm"][key], 3, f"holm {key}")
        tour, label = key.split(" ", 1)
        holm.append({"tour": tour, "set": label, "p": value})

    taus = s["definitions"]["taus"]
    power = {"taus": taus, "evens": [100 * (1 / (1 + math.exp(-t)) - 0.5) for t in taus], "rows": []}
    for tour in ("ATP", "WTA"):
        found = s["power"][tour]
        for test in ROBUSTNESS_TESTS:
            curve, bound = found["power"][test], found["upper_bound"][test]
            if test in want["power_at_0.2"][tour]:
                same(curve[taus.index(0.2)], want["power_at_0.2"][tour][test], 2, f"power {tour} {test}")
                same(bound, want["bounds"][tour][test], 3, f"bound {tour} {test}")
            power["rows"].append({"tour": tour, "test": test, "power": curve, "bound": bound,
                                  "bound_points": None if bound is None else 100 * (1 / (1 + math.exp(-bound)) - 0.5)})

    games, within, sensitivity = [], [], []
    for tour in ("ATP", "WTA"):
        g = s["games"][tour]
        pr = g["period"]
        games.append({
            "tour": tour, "matches": g["matches"], "per_match_sd": g["per_match_sd"],
            "spread": [{"set": label, **{k: g["spread"][label][k] for k in ("players", "ratio", "trait_sd", "p")}}
                       for label in SETS],
            "clutch": {k: g["clutch"][k] for k in ("players", "ratio", "p")},
            "split_half": {k: g["split_half"][k] for k in ("players", "r", "low", "high")},
            "players": pr["players"],
            "correlations": {k: {m: pr["correlations"][k][m] for m in ("r", "low", "high")} for k in ("big", "clutch", "regular")},
            "forecasts": {k: {"beta": pr["forecasts"][k]["beta"], "se": pr["forecasts"][k]["se"],
                              "p": pr["forecasts"][k]["permutation_p"]} for k in ("big", "clutch")},
        })
        w = s["within"][tour]
        within.append({
            "tour": tour, "eligible": w["eligible_share_big"],
            "spread": {label: w["spread"][label]["ratio"] for label in SETS}, "clutch": w["clutch"]["ratio"],
            "split_half": {k: w["split_half"][k] for k in ("r", "low", "high")},
            "correlations": {k: w["period"]["correlations"][k]["r"] for k in ("big", "clutch")},
            "forecasts": {k: {"beta": w["period"]["forecasts"][k]["beta"], "se": w["period"]["forecasts"][k]["se"],
                              "p": w["period"]["forecasts"][k]["permutation_p"]} for k in ("big", "clutch")},
        })
        for label, found in s["sensitivity"][tour].items():
            c, fb, fc = found["correlations"]["clutch"], found["forecasts"]["big"], found["forecasts"]["clutch"]
            sensitivity.append({"tour": tour, "label": label, "players": found["players"], "clutch_r": c["r"],
                                "clutch_low": c["low"], "clutch_high": c["high"], "big_beta": fb["beta"],
                                "big_p": fb["permutation_p"], "clutch_beta": fc["beta"], "clutch_p": fc["permutation_p"]})
    check_v2_rest(games, within, sensitivity)

    by_format = []
    for bo, (wins_ratio, wins_p, games_ratio, games_p) in PRINTED_FORMAT.items():
        row = s["format"][f"ATP bo{bo}"]
        same(row["wins"]["ratio"], wins_ratio, 2, f"format bo{bo} wins ratio")
        same(row["wins"]["p"], wins_p, 3, f"format bo{bo} wins p")
        same(row["games"]["ratio"], games_ratio, 2, f"format bo{bo} games ratio")
        same(row["games"]["p"], games_p, 3, f"format bo{bo} games p")
        by_format.append({"tour": "ATP", "best_of": bo, "big_matches": row["big_matches"],
                          "regular_matches": row["regular_matches"],
                          "wins": {k: row["wins"][k] for k in ("players", "ratio", "p")},
                          "games": {k: row["games"][k] for k in ("players", "ratio", "p")}})

    d = s["definitions"]
    return {"sims": {"null": d["null_sims"], "power": d["power_sims"], "permutations": d["permutations"],
                     "game_permutations": d["game_permutations"]},
            "slope_tests": slope_tests, "null": null, "holm": holm, "power": power, "games": games, "within": within,
            "sensitivity": sensitivity, "format": by_format,
            "sources": [{"file": f"results/phase4/experiments/{p.name}", "sha256": sha(p)}
                        for p in (path, path.with_suffix(".txt"))]}


# "ATP clutch spread within one format" table: best of -> (wins ratio, wins p, games ratio, games p).
PRINTED_FORMAT = {3: (1.19, 0.042, 1.28, 0.010), 5: (0.83, 0.849, 1.26, 0.077)}

# (section, tour, path) -> (printed value, decimal places). A path is dotted keys into the exported row; list items by
# index. Sensitivity paths are "<variant label>|<field>".
PRINTED_V2_REST = {
    # Game margins table.
    ("games", "ATP", "per_match_sd"): (0.127, 3), ("games", "WTA", "per_match_sd"): (0.158, 3),
    ("games", "ATP", "spread.0.ratio"): (1.21, 2), ("games", "ATP", "spread.0.p"): (0.098, 3),
    ("games", "ATP", "spread.2.ratio"): (1.23, 2), ("games", "ATP", "spread.2.p"): (0.038, 3),
    ("games", "ATP", "spread.3.ratio"): (1.69, 2), ("games", "WTA", "spread.3.ratio"): (1.97, 2),
    ("games", "WTA", "spread.0.ratio"): (1.48, 2), ("games", "WTA", "spread.0.p"): (0.007, 3),
    ("games", "ATP", "clutch.ratio"): (1.23, 2), ("games", "ATP", "clutch.p"): (0.022, 3),
    ("games", "WTA", "clutch.ratio"): (1.02, 2), ("games", "WTA", "clutch.p"): (0.409, 3),
    ("games", "ATP", "split_half.r"): (0.158, 3), ("games", "WTA", "split_half.r"): (0.066, 3),
    ("games", "ATP", "correlations.clutch.r"): (0.122, 3), ("games", "WTA", "correlations.clutch.r"): (0.363, 3),
    ("games", "WTA", "correlations.clutch.low"): (0.056, 3),
    ("games", "ATP", "forecasts.big.p"): (0.191, 3), ("games", "ATP", "forecasts.clutch.p"): (0.185, 3),
    ("games", "WTA", "forecasts.big.p"): (0.075, 3), ("games", "WTA", "forecasts.clutch.p"): (0.990, 3),
    # Within-tournament table.
    ("within", "ATP", "eligible"): (0.943, 3), ("within", "WTA", "eligible"): (0.943, 3),
    ("within", "ATP", "clutch"): (1.17, 2), ("within", "WTA", "clutch"): (0.97, 2),
    ("within", "ATP", "split_half.r"): (0.102, 3), ("within", "WTA", "split_half.r"): (0.064, 3),
    ("within", "ATP", "forecasts.big.p"): (0.237, 3), ("within", "ATP", "forecasts.clutch.p"): (0.212, 3),
    ("within", "WTA", "forecasts.big.p"): (0.110, 3), ("within", "WTA", "forecasts.clutch.p"): (0.962, 3),
    # Sensitivity table: the rows the reading cites.
    ("sensitivity", "ATP", "periods 2008-2015 / 2016-2026|clutch_r"): (0.336, 3),
    ("sensitivity", "WTA", "semi-finals and finals only|clutch_r"): (-0.327, 3),
    ("sensitivity", "WTA", "shrinkage 10|big_p"): (0.088, 3),
    ("sensitivity", "ATP", "shrinkage 100|clutch_p"): (0.101, 3),
}


def check_v2_rest(games, within, sensitivity):
    """Game-margin, within-tournament and sensitivity figures against the report's printed tables."""
    for (section, tour, path), (value, places) in PRINTED_V2_REST.items():
        if section == "sensitivity":
            label, field = path.split("|")
            found = next(r for r in sensitivity if r["tour"] == tour and r["label"] == label)[field]
        else:
            found = next(r for r in {"games": games, "within": within}[section] if r["tour"] == tour)
            for part in path.split("."):
                found = found[int(part)] if part.isdigit() else found[part]
        same(found, value, places, f"{section} {tour} {path}")


def build():
    historical ={"schema_version": "1", "phase2": PHASE2, "phase3": phase3(), "phase4": phase4()}
    market = {"schema_version": "1", **phase5()}
    return historical, market


def main():
    try:
        historical, market = build()
        myth = big_match()
    except Mismatch as error:
        print(f"refused: {error}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, doc in (("historical.json", historical), ("market.json", market), ("big-match.json", myth)):
        (OUT / name).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}/historical.json, market.json and big-match.json; "
          "every headline matches its report")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The historical research figures the website shows (Phases 2-5), exported once from the saved results.

    python -m web.publisher.research          writes web/content/research/{historical,market,big-match}.json

Run by hand when the research changes, not on the twice-daily schedule. Every headline number is either recomputed from
a saved prediction file or read from a saved results file, and then **asserted equal to the value printed in the
published report** (to the report's precision). A mismatch stops the export. Each output names its source files and
their sha256, so the figures are traceable. Only aggregates leave: no match-level rows, no prices, and no player data
except one illustrative table in working paper 1 (big-match wins against expectation for twenty named players, each a
sum over public tour results). Working paper 1 (version 3) checks its quoted headline figures (HEADLINES) instead of
a printed report, because its page reads every other figure from the export.

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


def _load(name):
    path = RESULTS / "phase4" / "experiments" / name
    return path, json.loads(path.read_text(encoding="utf-8"))


def _source(path):
    return {"file": f"results/phase4/experiments/{path.name}", "sha256": sha(path)}


def _finite(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


# Working paper 1, version 3: the headline figures quoted in the paper's abstract, the research README
# (docs/research/big-matches/README.md) and the portfolio summary. Each is asserted against the analysis output to
# the precision printed there, so a rerun that moves a quoted number stops the export. Everything else on the page is
# read from the exported file directly. (section, key) -> (printed value, decimal places).
HEADLINES = {
    ("counts", "matches"): (130460, 0), ("counts", "big_matches"): (14086, 0),
    ("spread", "ATP all big matches"): (1.10, 2), ("spread", "WTA all big matches"): (0.93, 2),
    ("spread", "ATP finals only"): (1.07, 2), ("spread", "WTA finals only"): (1.16, 2),
    ("split_half", "ATP"): (0.121, 3), ("split_half", "WTA"): (0.044, 3),
    ("calibration", "WTA bo3 big"): (0.755, 3), ("calibration", "WTA bo3 regular"): (0.821, 3),
    ("calibration", "WTA bo3 cluster_p"): (0.016, 3),
    ("forecast", "WTA M0 minus M1 log loss"): (0.00089, 5),
    ("forecast", "both big minus M1 log loss"): (0.00003, 5),
    ("forecast", "both clutch minus M1 log loss"): (0.00007, 5),
}


def headline_values(v1s, rob, fc):
    """The headline figures as computed, keyed like HEADLINES. Filled in by big_match()."""
    both = fc["forecast"]["both|big matches"]["models"]
    wta = fc["forecast"]["WTA|big matches"]["models"]
    cal = fc["calibration"]["window"]["WTA bo3"]
    values = {
        ("counts", "matches"): v1s["matches"], ("counts", "big_matches"): v1s["big"],
        ("calibration", "WTA bo3 big"): cal["big"], ("calibration", "WTA bo3 regular"): cal["regular"],
        ("calibration", "WTA bo3 cluster_p"): cal["cluster_p"],
        ("forecast", "WTA M0 minus M1 log loss"): wta["M0"]["log_loss_diff"],
        ("forecast", "both big minus M1 log loss"): both["big"]["log_loss_diff"],
        ("forecast", "both clutch minus M1 log loss"): both["clutch"]["log_loss_diff"],
    }
    for key in ("ATP all big matches", "WTA all big matches", "ATP finals only", "WTA finals only"):
        values[("spread", key)] = v1s["spread"][key]["ratio"]
    for tour in ("ATP", "WTA"):
        values[("split_half", tour)] = v1s["split_half"][tour]["r"]
    return values


def check_headlines(values, printed=None):
    printed = HEADLINES if printed is None else printed
    for key, (value, places) in printed.items():
        same(values[key], value, places, f"headline {key}")


def big_match():
    """Working paper 1 ("Do players choke in big matches?"), version 3: every figure the paper shows, from the four
    analysis outputs (matchup_dna.posthoc_big_match, _robustness, _players, _forecast). Aggregates only, except the
    illustrative table of twenty named players' big-match records (sums over public tour results)."""
    v1_path, s = _load("posthoc_big_match.json")
    rob_path, rb = _load("posthoc_big_match_robustness.json")
    pl_path, pl = _load("posthoc_big_match_players.json")
    fc_path, fc = _load("posthoc_big_match_forecast.json")
    if not rb["reproduction"]["checked"] or rb["reproduction"]["largest_difference"] > 1e-9:
        raise Mismatch("the robustness run did not reproduce the main analysis point estimates")
    text = v1_path.with_suffix(".txt").read_text(encoding="utf-8")
    counts = re.search(r"Window 2000 - May 2026: ([\d,]+) main-tour matches, ([\d,]+) of them big", text)
    matches, big = (int(counts.group(i).replace(",", "")) for i in (1, 2))
    if (matches, big) != (rb["reproduction"]["matches"], rb["reproduction"]["big"]):
        raise Mismatch("the main analysis and the robustness run disagree on the match counts")
    definitions = s["definitions"]
    if tuple(definitions["window"]) != tuple(fc["definitions"]["window"]):
        raise Mismatch("the forecast run used a different window")
    v1s = {"matches": matches, "big": big, "spread": s["spread"], "split_half": s["split_half"]}
    check_headlines(headline_values(v1s, rb, fc))

    calibration = []
    for key, slope in s["calibration_slopes"].items():
        tour, kind, bo = key.split()
        calibration.append({"tour": tour, "kind": kind, "best_of": int(bo[2:]), "slope": slope})
    spread = [{"tour": key.split(" ", 1)[0], "set": key.split(" ", 1)[1], "players": row["players"],
               "ratio": row["ratio"], "observed_sd": row["observed_sd"], "noise_sd": row["noise_sd"],
               "trait_sd": row["trait_sd"], "implied_k": _finite(row["implied_k"])} for key, row in s["spread"].items()]
    split_half = {tour: {k: row[k] for k in ("players", "r", "low", "high", "spearman_brown")}
                  for tour, row in s["split_half"].items()}
    period_split = {}
    for tour, row in s["period_split"].items():
        period_split[tour] = {
            "players": row["big-match score"]["players"],
            "correlations": {label.removesuffix(" score"): {k: row[label][k] for k in ("r", "low", "high")}
                             for label in ("big-match score", "clutch score", "regular-match score")},
            "forecasts": {label.removeprefix("forecast with ").removesuffix(" score"): {
                k: row[label][k] for k in ("matches", "with_history", "beta", "se", "log_loss_change", "permutation_p")}
                for label in ("forecast with big-match score", "forecast with clutch score")},
        }
    streak = {"finals": 29, "p_win": 0.6, "two": losing_run(29, 0.6, 2), "three": losing_run(29, 0.6, 3)}

    return {
        "schema_version": "3", "evidence": "post-hoc",
        "window": "2000 – 24 May 2026", "last_day": "2026-05-24", "matches": matches, "big_matches": big,
        "shrink": definitions["shrink"], "min_big": definitions["min_big"], "periods": ["2012–2018", "2019 – May 2026"],
        "calibration": calibration, "spread": spread, "split_half": split_half, "period_split": period_split,
        "streak": streak,
        "robustness": big_match_robustness(rb),
        "players": big_match_players(pl),
        "forecast": big_match_forecast(fc),
        "provenance": {"data_files": len(fc["provenance"]["data_files"]),
                       "data_sha256": hashlib.sha256("".join(f["sha256"] for f in fc["provenance"]["data_files"]).encode()).hexdigest(),
                       "code_commit_at_run": fc["provenance"]["code_commit_at_run"],
                       "analysis_code_committed": fc["provenance"].get("analysis_code_committed")},
        "sources": [_source(p) for p in (v1_path, v1_path.with_suffix(".txt"), rob_path, rob_path.with_suffix(".txt"),
                                         pl_path, fc_path, fc_path.with_suffix(".txt"))],
    }


ROBUSTNESS_TESTS = ("ratio finals only", "ratio semi-finals + finals", "ratio all big matches", "ratio regular matches",
                    "clutch ratio", "split-half r", "period r big", "period r clutch", "forecast z big", "forecast z clutch")
SETS = ("finals only", "semi-finals + finals", "all big matches", "regular matches")


def big_match_robustness(s):
    """Simulation tests, power and bounds, game margins, within-tournament ratings, sensitivity and the format check
    (matchup_dna.posthoc_big_match_robustness, version 3)."""
    null = []
    for tour in ("ATP", "WTA"):
        found = s["null"][tour]
        for test in ROBUSTNESS_TESTS:
            entry = {"tour": tour, "test": test, "observed": found["observed"][test],
                     "critical": found["critical"][test], "p": found["p"][test]}
            if test in s["holm"]["family"]:
                entry["holm"] = s["holm"]["both_tours"][f"{tour}|{test}"]
                entry["holm_tour"] = s["holm"]["by_tour"][f"{tour}|{test}"]
            null.append(entry)
    taus = s["definitions"]["taus"]
    evens = lambda t: 100 * (1 / (1 + math.exp(-t)) - 0.5)
    power = {"taus": taus, "evens": [evens(t) for t in taus], "rows": []}
    for tour in ("ATP", "WTA"):
        found = s["power"][tour]
        for test in ROBUSTNESS_TESTS:
            bound, mc = found["upper_bound"][test], found["bound_mc"][test]
            power["rows"].append({"tour": tour, "test": test, "power": found["power"][test], "bound": bound,
                                  "bound_points": None if bound is None else evens(bound),
                                  "bound_low_points": None if mc["low"] is None else evens(mc["low"]),
                                  "bound_high_points": None if mc["high"] is None else evens(mc["high"])})
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
            c, fb, fcl = found["correlations"]["clutch"], found["forecasts"]["big"], found["forecasts"]["clutch"]
            sensitivity.append({"tour": tour, "label": label, "players": found["players"], "clutch_r": c["r"],
                                "clutch_low": c["low"], "clutch_high": c["high"], "big_beta": fb["beta"],
                                "big_p": fb["permutation_p"], "clutch_beta": fcl["beta"], "clutch_p": fcl["permutation_p"]})
    by_format = []
    for key, row in s["format"].items():
        by_format.append({"tour": "ATP", "best_of": int(key[-1]), "big_matches": row["big_matches"],
                          "regular_matches": row["regular_matches"],
                          "wins": {k: row["wins"][k] for k in ("players", "ratio", "p")},
                          "games": {k: row["games"][k] for k in ("players", "ratio", "p")}})
    d = s["definitions"]
    return {"sims": {"null": d["null_sims"], "power": d["power_sims"], "permutations": d["permutations"],
                     "game_permutations": d["game_permutations"]},
            "family": s["holm"]["family"], "null": null, "power": power, "games": games, "within": within,
            "sensitivity": sensitivity, "format": by_format}


def big_match_players(s):
    """The five highest and five lowest 2012-2018 big-match scores on each tour, and the same players afterwards."""
    tours = []
    for tour in ("ATP", "WTA"):
        found = s["tours"][tour]
        keep = lambda p: {"name": p["name"], **{period: {k: p[period][k] for k in ("big", "won", "expected", "score", "clutch")}
                                                for period in ("early", "late")}}
        tours.append({"tour": tour, "players": found["players"], "shown": s["definitions"]["shown"],
                      "top": [keep(p) for p in found["top"]], "bottom": [keep(p) for p in found["bottom"]],
                      "means": {g: {"score": m["score"], "clutch": m["clutch"]} for g, m in found["means"].items()},
                      "top_still_positive": found["top_still_positive"],
                      "bottom_still_negative": found["bottom_still_negative"]})
    return {"tours": tours}


def big_match_forecast(s):
    """Calibration diagnostics and the out-of-sample evaluation (matchup_dna.posthoc_big_match_forecast)."""
    calibration = {"window": [{"key": k, **v} for k, v in s["calibration"]["window"].items()],
                   "periods": [{"period": p, "key": k, **v} for p, rows in s["calibration"]["periods"].items()
                               for k, v in rows.items()]}
    evaluation = []
    for key, found in s["forecast"].items():
        tour, subset = key.split("|")
        evaluation.append({"tour": tour, "subset": subset, "matches": found["matches"], "editions": found["editions"],
                           "models": [{"model": m, **v} for m, v in found["models"].items()]})
    d = s["definitions"]
    return {"first_eval_year": d["first_eval_year"], "first_fit_year": d["first_fit_year"],
            "recent_years": d["recent_years"], "bootstraps": d["bootstraps"], "models": d["models"],
            "calibration": calibration, "evaluation": evaluation,
            "by_year": [{"year": int(y), **v} for y, v in s["by_year"].items()],
            "betas": {k: {tour: [{"year": int(y), "beta": b} for y, b in years.items()] for tour, years in t.items()}
                      for k, t in s["betas"].items() if k in ("big", "clutch")}}


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

"""The historical research figures the website shows (Phases 2-5), exported once from the saved results.

    python -m web.publisher.research          writes web/content/research/{historical,market}.json

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


def build():
    historical = {"schema_version": "1", "phase2": PHASE2, "phase3": phase3(), "phase4": phase4()}
    market = {"schema_version": "1", **phase5()}
    return historical, market


def main():
    try:
        historical, market = build()
    except Mismatch as error:
        print(f"refused: {error}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, doc in (("historical.json", historical), ("market.json", market)):
        (OUT / name).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}/historical.json and market.json; every headline matches its report")
    return 0


if __name__ == "__main__":
    sys.exit(main())

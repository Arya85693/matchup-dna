"""Phase 5: the quantitative research engine. The frozen models' probabilities against opening market prices.

    python -m matchup_dna.phase5_experiment dataset    linked model matches with opening prices -> results/phase5/
    python -m matchup_dna.phase5_experiment develop    2021-2023 only: margin method, blend weights, every analysis
    python -m matchup_dna.phase5_experiment freeze     writes experiments/phase5_frozen_protocol.json (never overwritten)
    python -m matchup_dna.phase5_experiment evaluate   January 2024 - October 2026, once, under the frozen protocol

Questions, fixed before any evaluation row is opened (the brief, sections 27-31):
  Q1 accuracy     Do Phase 4's probabilities beat the margin-free opening market (log loss, Brier)?
  Q2 information  Does a blend of market and model, with weights fitted on 2021-2023, beat the market alone?
  Q3 signal       Does the model-minus-market discrepancy predict the part of the result the market misses?
  Q4 where        Is any gap concentrated by year, surface, level, tour, price range, or ranking? (descriptive)
  Q5 decisions    Does a paper rule that backs Phase 4's expected value at opening prices survive costs, risk and
                  uncertainty? Does it beat the closing line?

The decision rules below are set in this file before the development run, not tuned on it. Development may choose
only the margin method (the one with the lowest opening-market log loss on 2021-2023) and the blend weights.
"""
import argparse
import datetime
import json
import math
from collections import defaultdict

import numpy as np

from matchup_dna import backtest, market, signals, uncertainty, valuebetennis
from matchup_dna.experiment import EXPERIMENTS_DIR, ROOT, Output, manifest, scores, sha256
from matchup_dna.phase5_dataset import DATASET_PATH, PHASE5_DIR, PREDICTIONS, build_dataset, load, save_dataset

PROTOCOL_PATH = EXPERIMENTS_DIR / "phase5_frozen_protocol.json"
LOG_PATH = EXPERIMENTS_DIR / "phase5_log.md"
OUTPUT_DIR = PHASE5_DIR / "experiments"
SETTINGS_PATH = PHASE5_DIR / "settings.json"
EVALUATION_DIR = PHASE5_DIR / "evaluation"
MODELS = ("Phase 4", "Phase 3", "Elo", "Surface Elo")
PRIMARY_MODEL = "Phase 4"
BLEND_MODELS = ("Phase 4", "Phase 3")
# Paper rules, fixed before the development run.
RULES = {
    "primary": {"probability": "Phase 4", "threshold": 0.05, "sizing": "flat", "haircut": 0.0},
    "primary, 2% price haircut": {"probability": "Phase 4", "threshold": 0.05, "sizing": "flat", "haircut": 0.02},
    "primary, quarter Kelly capped at 2%": {"probability": "Phase 4", "threshold": 0.05, "sizing": "kelly",
                                            "haircut": 0.0},
    "secondary: frozen blend": {"probability": "blend Phase 4", "threshold": 0.02, "sizing": "flat", "haircut": 0.0},
}
CODE_FILES = ("matchup_dna/valuebetennis.py", "matchup_dna/market.py", "matchup_dna/market_link.py",
              "matchup_dna/phase5_dataset.py", "matchup_dna/signals.py", "matchup_dna/backtest.py",
              "matchup_dna/uncertainty.py", "matchup_dna/phase5_experiment.py")
LEVEL_GROUPS = {"G": "Grand Slam", "M": "Masters / WTA 1000", "PM": "Masters / WTA 1000", "A": "other tour events",
                "P": "other tour events", "I": "other tour events", "D": "Davis / BJK Cup"}


# ---------------------------------------------------------------- slices (Q4), fixed in advance

def favourite_bucket(p):
    q = max(p, 1 - p)
    return "market favourite 50-60%" if q < 0.6 else "60-75%" if q < 0.75 else "75-90%" if q < 0.9 else "90%+"


def rank_group(row):
    ranks = [r for r in (row["a_rank"], row["b_rank"]) if r is not None]
    if len(ranks) < 2:
        return "a rank missing"
    best = min(ranks)
    return "better-ranked player top 20" if best <= 20 else "21-100" if best <= 100 else "outside 100"


SLICES = {
    "year": lambda r: r["start"][:4],
    "tour": lambda r: r["tour"],
    "surface": lambda r: r["surface"] or "unknown",
    "level": lambda r: LEVEL_GROUPS.get(r["tourney_level"], "Finals, Olympics, ITF-level"),
    "market favourite's probability": lambda r: favourite_bucket(r["p_market"]),
    "ranking": rank_group,
}


# ---------------------------------------------------------------- shared analysis

def prepare(rows, settings):
    method = settings["margin_method"]
    for r in rows:
        r["p_market"] = signals.market_probability(r["open_a"], r["open_b"], method)
        r["p_close"] = (signals.market_probability(r["close_a"], r["close_b"], method)
                        if r["close_a"] is not None and r["close_b"] is not None else None)
        for name in BLEND_MODELS:
            r[f"blend {name}"] = float(signals.blend(settings["blend_weights"][name], [r["p_market"]], [r[name]])[0])
    return rows


def gap_record(p_new, p_old, y, clusters):
    from matchup_dna.experiment import match_log_loss
    d = match_log_loss(np.asarray(p_new), y) - match_log_loss(np.asarray(p_old), y)
    mean, se = uncertainty.clustered_mean(d, clusters)
    low, high, p = uncertainty.interval(mean, se)
    brier = (np.asarray(p_new) - y) ** 2 - (np.asarray(p_old) - y) ** 2
    b_mean, b_se = uncertainty.clustered_mean(brier, clusters)
    return {"matches": len(y), "gap": mean, "se": se, "low": low, "high": high, "p": p, "brier_gap": b_mean,
            "brier_se": b_se}


def describe_gap(out, label, g):
    out(f"   {label:<52} {g['matches']:>6,}  {g['gap']:+.4f} (se {g['se']:.4f}; {g['low']:+.4f} to {g['high']:+.4f}; "
        f"p {g['p']:.3g})  Brier {g['brier_gap']:+.4f} (se {g['brier_se']:.4f})")


def analyse(out, rows, settings, title):
    """Every analysis on one set of rows with fixed settings. Returns a JSON-ready summary."""
    from matchup_dna.selection import calibration_line
    y = np.array([r["a_won"] for r in rows], dtype=float)
    clusters = [r["tourney_date"] for r in rows]
    market_p = np.array([r["p_market"] for r in rows])
    found = {"title": title, "matches": len(rows)}

    out(f"\n{title}: {len(rows):,} matches with opening prices (margin removed by the {settings['margin_method']} method)")
    out(f"   {'forecast':<28} {'log loss':>9} {'Brier':>8} {'accuracy':>9}  calibration a, b")
    found["scores"] = {}
    for name, p in [("opening market", market_p)] + [(m, np.array([r[m] for r in rows])) for m in MODELS] + \
            [(f"blend {m} (frozen weights)", np.array([r[f"blend {m}"] for r in rows])) for m in BLEND_MODELS]:
        s = scores(p, y)
        a, b = calibration_line(p, y)
        found["scores"][name] = {**s, "calibration": [a, b]}
        out(f"   {name:<28} {s['log_loss']:>9.4f} {s['brier']:>8.4f} {s['accuracy']:>9.2%}  {a:+.3f}, {b:.3f}")

    out("\n   Q1 and Q2. Log loss per match minus the opening market's (negative = better than the market); se clustered "
        "by tournament date")
    found["gaps"] = {}
    for name in MODELS + tuple(f"blend {m}" for m in BLEND_MODELS):
        g = gap_record([r[name] for r in rows], market_p, y, clusters)
        found["gaps"][name] = g
        describe_gap(out, name + (" (frozen weights)" if name.startswith("blend") else ""), g)

    out("\n   Q3. Information slope b of (result - market) on (model - market); b > 0: the model's disagreement carries "
        "information")
    found["slopes"] = {}
    for name in MODELS:
        b, se = signals.information_slope([r[name] for r in rows], market_p, y, clusters)
        low, high, p = uncertainty.interval(b, se)
        found["slopes"][name] = {"b": b, "se": se, "low": low, "high": high, "p": p}
        out(f"   {name:<28} b {b:+.3f} (se {se:.3f}; {low:+.3f} to {high:+.3f}; p {p:.3g})")
    out("\n   Phase 4 minus market, by size of disagreement (player A's side; A is random)")
    found["buckets"] = signals.bucket_table([r[PRIMARY_MODEL] for r in rows], market_p, y)
    for b in found["buckets"]:
        out(f"      {b['low']:+.2f} to {b['high']:+.2f}: {b['matches']:>6,} matches; market {b['market']:.3f}, "
            f"Phase 4 {b['model']:.3f}, observed {b['observed']:.3f}")

    closed = [r for r in rows if r["p_close"] is not None]
    if closed:
        yc = np.array([r["a_won"] for r in closed], dtype=float)
        cc = [r["tourney_date"] for r in closed]
        out(f"\n   Closing line ({len(closed):,} matches with closing prices; a benchmark, never a decision price)")
        found["closing"] = {
            "closing minus opening": gap_record([r["p_close"] for r in closed], [r["p_market"] for r in closed], yc, cc),
            "Phase 4 minus closing": gap_record([r[PRIMARY_MODEL] for r in closed], [r["p_close"] for r in closed], yc, cc)}
        for label, g in found["closing"].items():
            describe_gap(out, label, g)

    out("\n   Q4. Phase 4 minus opening market, by slice (descriptive; "
        f"{sum(len({key(r) for r in rows}) for key in SLICES.values())} slices, so about one in twenty will look "
        "notable by chance)")
    found["slices"] = defaultdict(dict)
    for slice_name, key in SLICES.items():
        groups = defaultdict(list)
        for r in rows:
            groups[key(r)].append(r)
        for group in sorted(groups):
            subset = groups[group]
            g = gap_record([r[PRIMARY_MODEL] for r in subset], [r["p_market"] for r in subset],
                           np.array([r["a_won"] for r in subset], dtype=float), [r["tourney_date"] for r in subset])
            found["slices"][slice_name][group] = g
            describe_gap(out, f"{slice_name}: {group}", g)

    out("\n   Q5. Paper rules at opening prices (simulated; no real bet). ROI = profit per unit staked; interval from "
        f"{uncertainty.DRAWS} bootstrap draws of whole tournament dates")
    found["backtests"] = {}
    for name, rule in RULES.items():
        key = rule["probability"]
        bets, m = backtest.run(rows, lambda r: r[key], rule["threshold"], rule["sizing"], haircut=rule["haircut"])
        if rule["sizing"] == "flat" and bets:
            samples = uncertainty.cluster_bootstrap(bets, lambda b: b["tourney_date"],
                                                    lambda sample: sum(b["profit"] for b in sample) / len(sample))
            m["roi_interval"] = uncertainty.percentile_interval(samples)
            m["roi_share_of_draws_above_zero"] = sum(s > 0 for s in samples) / len(samples)
        found["backtests"][name] = m
        extra = (f"; ROI 95% {m['roi_interval'][0]:+.3f} to {m['roi_interval'][1]:+.3f}" if "roi_interval" in m else
                 f"; final bankroll {m['final_bankroll']:.3f}" if m["final_bankroll"] is not None else "")
        out(f"   {name}: {m['bets']:,} bets of {len(rows):,} matches; ROI {m['roi']:+.3f}{extra}; expected ROI if the "
            f"market is right {m['expected_roi_if_market_right']:+.3f}; hit rate {m['hit_rate']:.1%} at mean odds "
            f"{m['mean_odds']:.2f}; max drawdown {m['max_drawdown']:.2f}{'' if rule['sizing'] == 'flat' else ' of bankroll'}"
            f" {'units' if rule['sizing'] == 'flat' else ''}; longest losing run {m['longest_losing_run']}; "
            f"closing line value {m['mean_clv']:+.3f} on {m['clv_bets']:,} bets, {m['share_beating_close']:.1%} beat the close")
    found["slices"] = dict(found["slices"])
    return found


# ---------------------------------------------------------------- commands

def save(name, out, inputs, summary, extra=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{name}.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    record = manifest(name, inputs, extra)
    (OUTPUT_DIR / f"{name}_manifest.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", encoding="utf-8") as log:
        if new:
            log.write("# Phase 5 experiment log\n\nOne entry per run, appended by `python -m matchup_dna.phase5_experiment`.\n")
        log.write(f"\n## {record['created']} · {name}\n\ncommit `{record['git_commit']}`\n\n")
        for line in summary:
            log.write(f"- {line}\n")


def dataset():
    out = Output()
    rows, result = build_dataset()
    save_dataset(rows)
    counts = defaultdict(int)
    for r in rows:
        counts[(r["split"], r["period"])] += 1
    out(f"Linked model matches with usable opening prices: {len(rows):,}")
    for (split, period), n in sorted(counts.items()):
        out(f"   {split:<12} {period:<30} {n:>7,}")
    out(f"   with closing prices: {sum(r['close_a'] is not None for r in rows):,}")
    out(f"   dataset sha256 {sha256(DATASET_PATH)}")
    save("dataset", out, valuebetennis.files() + [PREDICTIONS, DATASET_PATH],
         [f"{len(rows):,} linked matches with opening prices ({counts[('development', '2021-2023 validation')]:,} development)",
          f"dataset sha256 {sha256(DATASET_PATH)[:12]}"])
    print("\n".join(out.lines))


def develop():
    from matchup_dna.experiment import match_log_loss
    out = Output()
    rows = load("development")
    y = np.array([r["a_won"] for r in rows], dtype=float)
    out("PHASE 5 DEVELOPMENT, 2021-2023 only. The evaluation rows (January 2024 onward) are not opened.")
    out("\nMargin method: opening-market log loss on the development matches")
    losses = {}
    for method in market.METHODS:
        p = np.array([signals.market_probability(r["open_a"], r["open_b"], method) for r in rows])
        losses[method] = float(match_log_loss(p, y).mean())
        out(f"   {method:<15} {losses[method]:.5f}")
    method = min(losses, key=losses.get)
    out(f"   chosen: {method}")
    p_market = np.array([signals.market_probability(r["open_a"], r["open_b"], method) for r in rows])
    weights = {}
    out("\nBlend weights, logit P = w_market logit(market) + w_model logit(model), fitted on these matches")
    for name in BLEND_MODELS:
        w = signals.fit_blend(p_market, [r[name] for r in rows], y)
        samples = uncertainty.cluster_bootstrap(
            list(range(len(rows))), lambda i: rows[i]["tourney_date"],
            lambda idx: signals.fit_blend(p_market[idx], np.array([rows[i][name] for i in idx]), y[idx])[1], draws=400)
        low, high = uncertainty.percentile_interval(samples)
        weights[name] = list(w)
        out(f"   {name}: market {w[0]:.3f}, model {w[1]:+.3f} (model weight 95% {low:+.3f} to {high:+.3f}, "
            f"400 tournament-date bootstrap draws)")
    settings = {"margin_method": method, "margin_method_log_loss": losses, "blend_weights": weights,
                "fitted_on": "2021-2023 development matches", "rules": RULES}
    summary = analyse(out, prepare(rows, settings), settings,
                      "DEVELOPMENT 2021-2023 (in-sample for the blend and the margin method)")
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    (PHASE5_DIR / "development.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    g = summary["gaps"][PRIMARY_MODEL]
    save("develop", out, [DATASET_PATH], [
        f"development matches {len(rows):,}; margin method {method}",
        f"Phase 4 minus opening market {g['gap']:+.4f} (se {g['se']:.4f})",
        f"blend weights {json.dumps(weights)}"])
    print("\n".join(out.lines))


def code_hashes():
    return {path: sha256(ROOT / path) for path in CODE_FILES}


def input_hashes():
    paths = [DATASET_PATH, SETTINGS_PATH, PREDICTIONS] + valuebetennis.files()
    return {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in paths}


def freeze():
    from matchup_dna.phase4_experiment import head_commit
    if PROTOCOL_PATH.exists():
        raise SystemExit(f"{PROTOCOL_PATH} already exists. It is never overwritten.")
    if not SETTINGS_PATH.exists():
        raise SystemExit("Run `develop` first; the protocol records its choices.")
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    protocol = {
        "phase": 5, "frozen": datetime.datetime.now().isoformat(timespec="seconds"), "base_commit": head_commit(),
        "evaluation": {"rows": "linked model matches with usable opening prices, January 2024 - October 2026",
                       "command": "python -m matchup_dna.phase5_experiment evaluate (refuses to run twice)"},
        "development": "2021-2023 (the Phase 4 validation years); its model-against-market result was first seen on "
                       "6 November 2026 by an earlier, removed draft",
        "status_of_the_evaluation_window": "the models' outcomes there were seen in Phases 3 and 4; the models were "
                                            "never compared with the market there",
        "decision_price": "opening price; the closing price is a benchmark only",
        "margin_method": settings["margin_method"], "blend_weights": settings["blend_weights"],
        "primary_model": PRIMARY_MODEL, "rules": RULES, "slices": list(SLICES),
        "questions": {
            "Q1": "Phase 4 minus opening market, log loss per match, se clustered by tourney_date",
            "Q2": "frozen Phase 4 blend minus opening market, log loss per match",
            "Q3": "information slope of Phase 4, b with clustered se",
            "Q4": "slices, descriptive only",
            "Q5": "primary paper rule ROI with a tournament-date bootstrap interval; closing line value"},
        "reporting_rule": "a result is called supported only if its 95% interval excludes zero in the stated "
                          "direction; slices are descriptive; nothing is changed after the evaluation is seen",
        "code_sha256": code_hashes(), "inputs_sha256": input_hashes(),
    }
    PROTOCOL_PATH.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(protocol, indent=2))
    print(f"\nWritten to {PROTOCOL_PATH}.")


def evaluate():
    if EVALUATION_DIR.exists():
        raise SystemExit(f"{EVALUATION_DIR} exists: the evaluation has run. It runs once.")
    if not PROTOCOL_PATH.exists():
        raise SystemExit("No frozen Phase 5 protocol. Run `freeze` first.")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    changed = [k for k, v in protocol["code_sha256"].items() if code_hashes().get(k) != v]
    changed += [k for k, v in protocol["inputs_sha256"].items() if input_hashes().get(k) != v]
    if changed:
        raise SystemExit("Code or inputs differ from the frozen protocol:\n" + "\n".join(changed))
    settings = {"margin_method": protocol["margin_method"], "blend_weights": protocol["blend_weights"]}
    out = Output()
    out("PHASE 5 EVALUATION, January 2024 - October 2026, run once under experiments/phase5_frozen_protocol.json "
        f"(sha256 {sha256(PROTOCOL_PATH)[:16]}, frozen {protocol['frozen']}).")
    out("The models' outcomes in this window were seen in Phases 3 and 4; their comparison with the market was not.")
    rows = prepare(load("evaluation", unseal_with=PROTOCOL_PATH), settings)
    summary = {"all": analyse(out, rows, settings, "EVALUATION, January 2024 - October 2026")}
    for period in ("2024-May 2026 retrospective", "Jun-Oct 2026 held-out"):
        subset = [r for r in rows if r["period"] == period]
        g = gap_record([r[PRIMARY_MODEL] for r in subset], [r["p_market"] for r in subset],
                       np.array([r["a_won"] for r in subset], dtype=float), [r["tourney_date"] for r in subset])
        summary[period] = g
        describe_gap(out, f"Phase 4 minus market, {period}", g)
    EVALUATION_DIR.mkdir(parents=True)
    (EVALUATION_DIR / "evaluation.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    (EVALUATION_DIR / "evaluation.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    g = summary["all"]["gaps"][PRIMARY_MODEL]
    b = summary["all"]["gaps"]["blend Phase 4"]
    save("evaluate", out, [PROTOCOL_PATH, DATASET_PATH], [
        f"evaluation matches {len(rows):,}",
        f"Q1 Phase 4 minus opening market {g['gap']:+.4f} (se {g['se']:.4f}; {g['low']:+.4f} to {g['high']:+.4f})",
        f"Q2 frozen blend minus market {b['gap']:+.4f} (se {b['se']:.4f}; {b['low']:+.4f} to {b['high']:+.4f})",
        f"Q5 primary rule ROI {summary['all']['backtests']['primary']['roi']:+.3f}"])
    print("\n".join(out.lines))


def main():
    parser = argparse.ArgumentParser(description="Phase 5 experiments")
    parser.add_argument("command", choices=["dataset", "develop", "freeze", "evaluate"])
    args = parser.parse_args()
    {"dataset": dataset, "develop": develop, "freeze": freeze, "evaluate": evaluate}[args.command]()


if __name__ == "__main__":
    main()

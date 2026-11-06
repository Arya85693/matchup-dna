"""POST-HOC descriptive analysis, not pre-registered: Phase 4 against the ranking, January 2021 - October 2026.

    python -m matchup_dna.posthoc_rank_history

Two comparisons on every ranking-eligible match (both ranks known and different), period by period:

1. Winner picks. Where Phase 4 and "the higher-ranked player wins" pick different players, exactly one is right. An
   exact two-sided sign test asks whether Phase 4's share differs from 50%. Matches in one tournament are not
   independent, so a second test uses the per-match difference in correct picks over all eligible matches, with
   standard errors clustered by tourney_date (the protocol's clustering).
2. Probabilities. A ranking-only logistic model, per tour, with one feature, log(rank of B / rank of A), and no
   intercept (so P(A) + P(B) = 1). It is fitted only on matches before each period, mirroring Phase 4's own fits:
   2010-2020 for 2021-2023, 2010-2023 for 2024 to May 2026, 2010 to May 2026 for June-October 2026. No setting is
   tuned. Phase 4 and this model are compared by log loss and Brier, paired, clustered by tourney_date.

Reads the saved per-match predictions of posthoc_longrun --corrected (June-October 2026 from the corrected,
post-unblinding rebuild of erratum 1) and the Phase 3 training rows; nothing in Phase 3 or Phase 4 is refitted.
2021-2023 chose the Phase 4 model and 2024 to May 2026 had already been examined, so only June-October 2026 was ever
unseen, and it too was examined before the corrected rebuild. This is historical evidence, not a confirmation.
"""
import csv
import json
import math
from collections import defaultdict

import numpy as np

from matchup_dna.elo import RESULTS_DIR
from matchup_dna.evaluate import clustered_standard_error
from matchup_dna.experiment import Output, paired_gap, scores
from matchup_dna.model import fit_logistic, sigmoid

TABLE = RESULTS_DIR / "phase4" / "experiments" / "posthoc_longrun_predictions_corrected.csv"
OUTPUT = RESULTS_DIR / "phase4" / "experiments" / "posthoc_rank_history.txt"
SUMMARY = RESULTS_DIR / "phase4" / "experiments" / "posthoc_rank_history.json"
PERIODS = ("2021-2023 validation", "2024-May 2026 retrospective", "Jun-Oct 2026 held-out")
# eligible matches, ranking correct, Phase 4 correct, as reported by posthoc_longrun --corrected
EXPECTED = {PERIODS[0]: (15821, 10187, 10515), PERIODS[1]: (13540, 8643, 8845), PERIODS[2]: (2430, 1585, 1597),
            "Pooled": (31791, 20415, 20957)}


def rank(value):
    return None if value in ("", None) else float(value)


def load_history():
    rows = []
    with open(TABLE, encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            rows.append({"match_id": row["match_id"], "tourney_date": int(row["tourney_date"]), "tour": row["tour"],
                         "period": row["period"], "a_won": int(row["a_won"]), "a_rank": rank(row["a_rank"]),
                         "b_rank": rank(row["b_rank"]), "Phase 3": float(row["Phase 3"]),
                         "Phase 4": float(row["Phase 4"])})
    return rows


def training_rows():
    from matchup_dna.features import load_split
    return [{"tour": r["tour"], "a_won": int(r["a_won"]), "a_rank": r["a_rank"], "b_rank": r["b_rank"]}
            for r in load_split("train")]


def eligible(row):
    return row["a_rank"] is not None and row["b_rank"] is not None and row["a_rank"] != row["b_rank"]


def feature(rows):
    return np.array([[math.log(r["b_rank"] / r["a_rank"])] for r in rows])


def ranking_model(fit_rows):
    """{tour: coefficient} of the one-feature, no-intercept logistic model, on rows with both ranks known."""
    found = {}
    for tour in ("ATP", "WTA"):
        usable = [r for r in fit_rows if r["tour"] == tour and r["a_rank"] is not None and r["b_rank"] is not None]
        coefficients, _ = fit_logistic(feature(usable), np.array([r["a_won"] for r in usable]), l2=0.0, intercept=False)
        found[tour] = (float(coefficients[0]), len(usable))
    return found


def ranking_predictions(rows, model):
    x = feature(rows)[:, 0]
    w = np.array([model[r["tour"]][0] for r in rows])
    return sigmoid(w * x)


def credit(p, y):
    return np.where(p == 0.5, 0.5, ((p > 0.5) == (y == 1)).astype(float))


def sign_test(wins, losses):
    n, k = wins + losses, min(wins, losses)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else float("nan")


def wilson(successes, n):
    z, p = 1.96, successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def picks(rows, model_name):
    """Head-to-head on ranking-eligible rows: the model against 'the higher-ranked player wins'."""
    y = np.array([r["a_won"] for r in rows])
    p = np.array([r[model_name] for r in rows])
    rank_picks_a = np.array([r["a_rank"] < r["b_rank"] for r in rows])
    rank_right = rank_picks_a == (y == 1)
    model_right = credit(p, y)
    differ = (p != 0.5) & ((p > 0.5) != rank_picks_a)
    won = int((model_right[differ] == 1).sum())
    lost = int(differ.sum()) - won
    difference = model_right - rank_right.astype(float)  # nonzero only where the picks differ (or the model is at 0.5)
    se = clustered_standard_error(list(difference), [r["tourney_date"] for r in rows])
    mean = float(difference.mean())
    low, high = wilson(won, won + lost) if won + lost else (float("nan"), float("nan"))
    return {"matches": len(rows), "model_correct": float(model_right.sum()), "ranking_correct": int(rank_right.sum()),
            "disagreements": won + lost, "disagreement_rate": (won + lost) / len(rows), "model_right": won,
            "ranking_right": lost, "model_share": won / (won + lost) if won + lost else float("nan"),
            "share_low": low, "share_high": high, "sign_test_p": sign_test(won, lost),
            "accuracy_gap": mean, "accuracy_gap_se": se,
            "clustered_p": math.erfc(abs(mean / se) / math.sqrt(2)) if se > 0 else float("nan"),
            "mean_confidence_on_disagreements": float(np.maximum(p, 1 - p)[differ].mean()) if differ.any() else None}


def probabilities(rows, p_rank):
    y = np.array([r["a_won"] for r in rows], dtype=float)
    p4 = np.array([r["Phase 4"] for r in rows])
    gap, se = paired_gap(p4, p_rank, y, [r["tourney_date"] for r in rows])
    brier_gap = ((p4 - y) ** 2 - (p_rank - y) ** 2)
    brier_se = clustered_standard_error(list(brier_gap), [r["tourney_date"] for r in rows])
    return {"phase4": scores(p4, y), "ranking_model": scores(p_rank, y), "log_loss_gap": gap, "se": se,
            "low": gap - 1.96 * se, "high": gap + 1.96 * se, "p": math.erfc(abs(gap / se) / math.sqrt(2)),
            "brier_gap": float(brier_gap.mean()), "brier_se": brier_se}


def main():
    out = Output()
    out("POST-HOC DESCRIPTIVE ANALYSIS, not pre-registered: Phase 4 against the ranking, January 2021 - October 2026.")
    out("2021-2023 chose the model; 2024 - May 2026 had been examined; June-October 2026 (corrected, erratum 1) was")
    out("examined before its rebuild. Historical evidence only, not an independent confirmation. Saved predictions")
    out("only; the ranking-only model is fitted on earlier matches only and tuned on nothing.")
    history = load_history()
    train = training_rows()
    by_period = {period: [r for r in history if r["period"] == period] for period in PERIODS}
    fits = {PERIODS[0]: train, PERIODS[1]: train + by_period[PERIODS[0]],
            PERIODS[2]: train + by_period[PERIODS[0]] + by_period[PERIODS[1]]}

    summary, scored = {}, []
    for period in PERIODS:
        model = ranking_model(fits[period])
        rows = [r for r in by_period[period] if eligible(r)]
        p_rank = ranking_predictions(rows, model)
        for r, p in zip(rows, p_rank):
            r["ranking model"] = float(p)
        scored += rows
        summary[period] = {"fit": {t: {"coefficient": c, "rows": n} for t, (c, n) in model.items()}}
    groups = {**{period: [r for r in scored if r["period"] == period] for period in PERIODS}, "Pooled": scored}

    out("\nReproduction (eligible matches; correct picks of the ranking and of Phase 4):")
    for name, rows in groups.items():
        found = (len(rows), sum(r["a_rank"] < r["b_rank"] if r["a_won"] else r["a_rank"] > r["b_rank"] for r in rows),
                 float(credit(np.array([r["Phase 4"] for r in rows]), np.array([r["a_won"] for r in rows])).sum()))
        ok = found == EXPECTED[name]
        out(f"   {name:<30} {found[0]:>6,} {found[1]:>7,} {found[2]:>9,g}  expected {EXPECTED[name]} -> "
            f"{'reproduced' if ok else 'DIFFERS'}")
        if not ok:
            raise SystemExit("The saved table does not reproduce the long-run ranking benchmark; stopping.")

    out("\nRanking-only model: coefficient on log(rank B / rank A) per tour, fitted on earlier matches only")
    for period in PERIODS:
        fit = summary[period]["fit"]
        out(f"   {period:<30} ATP {fit['ATP']['coefficient']:.4f} ({fit['ATP']['rows']:,} rows)   "
            f"WTA {fit['WTA']['coefficient']:.4f} ({fit['WTA']['rows']:,} rows)")

    out("\n1. WINNER PICKS: Phase 4 (and Phase 3) against 'the higher-ranked player wins'")
    out(f"   {'group':<42} {'matches':>7} {'differ':>7} {'model':>6} {'rank':>5} {'share':>6} {'95% interval':>15} "
        f"{'exact p':>8} {'clustered p':>11}")
    for model_name in ("Phase 4", "Phase 3"):
        for name, rows in groups.items():
            for tour in ("Both", "ATP", "WTA"):
                subset = rows if tour == "Both" else [r for r in rows if r["tour"] == tour]
                result = picks(subset, model_name)
                summary.setdefault(name, {}).setdefault("picks", {})[f"{model_name} {tour}"] = result
                out(f"   {model_name + ', ' + name + ', ' + tour:<42} {result['matches']:>7,} {result['disagreements']:>7,} "
                    f"{result['model_right']:>6,} {result['ranking_right']:>5,} {result['model_share']:>6.1%} "
                    f"{result['share_low']:>7.1%}-{result['share_high']:<7.1%} {result['sign_test_p']:>8.3f} "
                    f"{result['clustered_p']:>11.3f}")
        out()
    for name in groups:
        result = summary[name]["picks"]["Phase 4 Both"]
        out(f"   {name}: on disagreements Phase 4 gave its pick {result['mean_confidence_on_disagreements']:.3f} on "
            f"average and was right {result['model_share']:.3f}")

    out("\n2. PROBABILITIES: Phase 4 against the ranking-only logistic model (identical matches; negative = Phase 4 better)")
    out(f"   {'group':<36} {'matches':>7} {'P4 log loss':>11} {'rank log loss':>13} {'gap':>8} {'se':>7} "
        f"{'95% interval':>17} {'p':>7} {'P4 Brier':>8} {'rank Brier':>10} {'P4 acc':>7} {'rank acc':>8}")
    for name, rows in groups.items():
        for tour in ("Both", "ATP", "WTA"):
            subset = rows if tour == "Both" else [r for r in rows if r["tour"] == tour]
            result = probabilities(subset, np.array([r["ranking model"] for r in subset]))
            summary[name].setdefault("probabilities", {})[tour] = result
            out(f"   {name + ', ' + tour:<36} {len(subset):>7,} {result['phase4']['log_loss']:>11.4f} "
                f"{result['ranking_model']['log_loss']:>13.4f} {result['log_loss_gap']:>+8.4f} {result['se']:>7.4f} "
                f"{result['low']:>+8.4f} to {result['high']:>+7.4f} {result['p']:>7.3g} {result['phase4']['brier']:>8.4f} "
                f"{result['ranking_model']['brier']:>10.4f} {result['phase4']['accuracy']:>7.2%} "
                f"{result['ranking_model']['accuracy']:>8.2%}")
    out("\nPooled rows mix model versions (each period's own fits) and periods used for selection or already examined.")
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    print(f"\nWritten to {OUTPUT}")


if __name__ == "__main__":
    main()

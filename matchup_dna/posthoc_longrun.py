"""POST-HOC descriptive analysis of performance from January 2021 to October 2026. Not part of the pre-registered
Phase 4 evaluation, and not used to choose or change anything.

    python -m matchup_dna.posthoc_longrun

Methods compared on identical matches in each period: Phase 2 Elo and surface Elo (raw), the Phase 3 logistic
model, the Phase 4 logistic model, and "the higher-ranked player wins". Every prediction is chronological: it was
made by a model fitted only on matches before the period it predicts.

Where each period's predictions come from:

    2021-2023 (validation; used to choose the Phase 4 model)
        Elo, surface Elo, ranks: saved Phase 3 rows (results/phase3/validation.csv)
        Phase 3, Phase 4: not saved per match. Reproduced by re-executing the reported development fits (2010-2020
        rows only, frozen settings); accepted only if they reproduce the published validation scores exactly.
    January 2024 - May 2026 (retrospective; examined in Phase 3 and in Phase 4's retrospective check)
        Elo, surface Elo, Phase 3: saved by the Phase 3 final run (results/phase3/final/reserved_predictions.csv)
        ranks: saved Phase 3 rows (results/phase3/reserved_features.csv)
        Phase 4: not saved per match. Reproduced by re-executing the retrospective fit (2010-2023 rows, frozen
        protocol settings); accepted only if it reproduces the published retrospective scores exactly.
    June - October 2026 (the independent held-out evaluation)
        Phase 3 (P3-refit), Phase 4: saved by holdout --confirm (results/phase4/final/heldout_predictions.csv)
        Elo, surface Elo, ranks: not saved. Elo is an online rating with no fitting (settings fixed on 1990-2009),
        so it is replayed through the same held-out data pipeline; nothing is fitted or scored by that rebuild.
"""
import csv
import json
from collections import defaultdict

import numpy as np

from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import Output, scores, tour_rows
from matchup_dna.load import TOURS

OUTPUT = RESULTS_DIR / "phase4" / "experiments" / "posthoc_longrun.txt"
TABLE = RESULTS_DIR / "phase4" / "experiments" / "posthoc_longrun_predictions.csv"
METHODS = ("Elo", "Surface Elo", "Phase 3", "Phase 4")
PERIODS = ("2021-2023 validation", "2024-May 2026 retrospective", "Jun-Oct 2026 held-out")
PHASE3_L2 = {"ATP": 1000.0, "WTA": 100.0}
PUBLISHED = {  # combined log loss and accuracy as published, for the reproduction checks
    ("2021-2023 validation", "Phase 3"): (0.6095, 0.6610), ("2021-2023 validation", "Phase 4"): (0.6069, 0.6662),
    ("2024-May 2026 retrospective", "Phase 3"): (0.6128, 0.6558),
    ("2024-May 2026 retrospective", "Phase 4"): (0.6114, 0.6547),
    ("Jun-Oct 2026 held-out", "Phase 3"): (0.6148, 0.6511), ("Jun-Oct 2026 held-out", "Phase 4"): (0.6108, 0.6547),
}


def per_tour_predict(fit_rows, target_rows, make_model):
    p = np.empty(len(target_rows))
    for tour in TOURS:
        index = [i for i, row in enumerate(target_rows) if row["tour"] == tour]
        if index:
            p[index] = make_model(tour).fit(tour_rows(fit_rows, tour)).predict([target_rows[i] for i in index])
    return p


def entry(row, p, period):
    return {"match_id": row["match_id"], "tourney_date": row["tourney_date"], "tour": row["tour"], "period": period,
            "a_won": int(row["a_won"]), "a_rank": row.get("a_rank"), "b_rank": row.get("b_rank"), **p}


def validation_period():
    from matchup_dna.features import load_split
    from matchup_dna.model import LogisticModel
    from matchup_dna.phase4_experiment import load_selection
    from matchup_dna.phase4_features import load_phase4
    from matchup_dna.phase4_model import PHASE3_GROUPS, Phase4Logistic
    p3_train, p3_val = load_split("train"), load_split("validation")
    p3 = per_tour_predict(p3_train, p3_val, lambda tour: LogisticModel(PHASE3_GROUPS, PHASE3_L2[tour]))
    p4_train, p4_val = load_phase4("train"), load_phase4("validation")
    selection = load_selection()
    p4 = per_tour_predict(p4_train, p4_val, lambda tour: Phase4Logistic(
        selection["groups"], selection["l2"][tour], selection["representations"][tour]))
    p4_by_id = dict(zip((r["match_id"] for r in p4_val), p4))
    return [entry(row, {"Elo": row["elo_probability"], "Surface Elo": row["surface_elo_probability"],
                        "Phase 3": p3[i], "Phase 4": p4_by_id[row["match_id"]]}, PERIODS[0])
            for i, row in enumerate(p3_val)]


def retrospective_period(protocol):
    from matchup_dna.features import DATASET_DIR, FILES, parse_row
    from matchup_dna.phase4_experiment import PROTOCOL_PATH
    from matchup_dna.phase4_features import load_phase4
    from matchup_dna.phase4_model import Phase4Logistic
    with open(RESULTS_DIR / "phase3" / "final" / "reserved_predictions.csv", encoding="utf-8", newline="") as file:
        saved = {row["match_id"]: row for row in csv.DictReader(file)}
    with open(DATASET_DIR / FILES["reserved"], encoding="utf-8", newline="") as file:
        ranks = {row["match_id"]: parse_row(row) for row in csv.DictReader(file)}
    rows = load_phase4("retrospective", unseal_with=PROTOCOL_PATH)
    fit_rows = load_phase4("train") + load_phase4("validation")
    model = protocol["tournament_start"]["model"]
    p4 = per_tour_predict(fit_rows, rows, lambda tour: Phase4Logistic(
        tuple(model["groups"]), model["l2"][tour], model["representations"][tour]))
    found = []
    for row, p in zip(rows, p4):
        s = saved[row["match_id"]]
        assert s["a_id"] == str(row["a_id"]) and int(s["a_won"]) == row["a_won"]
        found.append(entry({**row, "a_rank": ranks[row["match_id"]]["a_rank"], "b_rank": ranks[row["match_id"]]["b_rank"]},
                           {"Elo": float(s["Elo"]), "Surface Elo": float(s["Surface Elo"]),
                            "Phase 3": float(s["Selected model"]), "Phase 4": p}, PERIODS[1]))
    return found


def held_out_period():
    from matchup_dna.phase4_experiment import HELD_OUT, PROTOCOL_PATH, provider_period
    with open(RESULTS_DIR / "phase4" / "final" / "heldout_predictions.csv", encoding="utf-8", newline="") as file:
        saved = {row["match_id"]: row for row in csv.DictReader(file)}
    rows, _, _, _ = provider_period(*HELD_OUT, unseal_with=PROTOCOL_PATH)
    rebuilt = {row["match_id"]: row for row in rows if row["tourney_date"] >= HELD_OUT[0]}
    missing = set(saved) - set(rebuilt)
    if missing:
        raise SystemExit(f"{len(missing)} saved held-out matches were not rebuilt; stopping.")
    found = []
    for match_id, s in saved.items():
        row = rebuilt[match_id]
        assert s["a_id"] == str(row["a_id"]) and int(s["a_won"]) == row["a_won"]
        found.append(entry(row, {"Elo": row["elo_probability"], "Surface Elo": row["surface_elo_probability"],
                                 "Phase 3": float(s["P3-refit"]), "Phase 4": float(s["P4-refit"])}, PERIODS[2]))
    return found


def ranking_pick(row):
    """1 if the higher-ranked player (lower rank number) won, 0 if not, None if a rank is missing or tied."""
    a, b = row["a_rank"], row["b_rank"]
    if a is None or b is None or a == b:
        return None
    return float((a < b) == bool(row["a_won"]))


def table(out, title, rows):
    """Methods on identical matches: the eligible rows have every prediction and two different known ranks."""
    eligible = [r for r in rows if ranking_pick(r) is not None]
    missing = sum(1 for r in rows if r["a_rank"] is None or r["b_rank"] is None)
    tied = sum(1 for r in rows if r["a_rank"] is not None and r["b_rank"] is not None and r["a_rank"] == r["b_rank"])
    out(f"\n{title}: {len(rows):,} matches; excluded {missing:,} with a missing rank and {tied:,} with tied ranks; "
        f"{len(eligible):,} eligible")
    out(f"   {'method':<26} {'tour':<5} {'matches':>8} {'correct':>9}  accuracy  log loss  Brier")
    results = {}
    for tour in ("ATP", "WTA", "Both"):
        subset = [r for r in eligible if tour == "Both" or r["tour"] == tour]
        if not subset:
            continue
        y = np.array([r["a_won"] for r in subset], dtype=float)
        for method in METHODS:
            s = scores(np.array([r[method] for r in subset], dtype=float), y)
            results[(tour, method)] = s
            out(f"   {method:<26} {tour:<5} {s['matches']:>8,} {s['accuracy'] * s['matches']:>9,.1f}  {s['accuracy']:>7.2%}"
                f"   {s['log_loss']:.4f}  {s['brier']:.4f}")
        hits = sum(ranking_pick(r) for r in subset)
        results[(tour, "Higher-ranked player")] = {"accuracy": hits / len(subset), "matches": len(subset)}
        out(f"   {'Higher-ranked player':<26} {tour:<5} {len(subset):>8,} {hits:>9,.1f}  {hits / len(subset):>7.2%}"
            f"   {'-':>6}  {'-':>6}")
    return results


def main():
    from matchup_dna.phase4_experiment import PROTOCOL_PATH
    out = Output()
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    out("POST-HOC DESCRIPTIVE ANALYSIS, January 2021 - October 2026. Not part of the pre-registered Phase 4 evaluation;")
    out("nothing here was used to choose or change any model. 2021-2023 was used to select the Phase 4 model; January")
    out("2024 - May 2026 had already been examined (Phase 3 final run, Phase 4 retrospective); only June - October 2026")
    out("was an independent Phase 4 held-out evaluation. Every prediction comes from a model fitted only on earlier matches.")

    rows = validation_period() + retrospective_period(protocol) + held_out_period()
    out("\nReproduction checks (all matches of each period, before the rank filter): combined log loss and accuracy")
    for period in PERIODS:
        subset = [r for r in rows if r["period"] == period]
        y = np.array([r["a_won"] for r in subset], dtype=float)
        for method in ("Phase 3", "Phase 4"):
            s = scores(np.array([r[method] for r in subset], dtype=float), y)
            published = PUBLISHED[(period, method)]
            ok = round(s["log_loss"], 4) == published[0] and round(s["accuracy"], 4) == published[1]
            out(f"   {period:<28} {method}: log loss {s['log_loss']:.4f}, accuracy {s['accuracy']:.2%}; published "
                f"{published[0]:.4f}, {published[1]:.2%} -> {'reproduced' if ok else 'DIFFERS'}")
            if not ok:
                raise SystemExit("A reproduced prediction set does not match its published scores; not reporting it.")

    out("\nBY PERIOD (each method on identical eligible matches)")
    by_period = {period: table(out, period, [r for r in rows if r["period"] == period]) for period in PERIODS}

    out("\nBY YEAR (2026 split into the retrospective January-May and the held-out June-October)")
    def year_label(row):
        year = row["tourney_date"] // 10000
        if year == 2026:
            return "2026 Jan-May (retrospective)" if row["period"] == PERIODS[1] else "2026 Jun-Oct (held-out)"
        return str(year)
    years = defaultdict(list)
    for row in rows:
        years[year_label(row)].append(row)
    for label in sorted(years):
        table(out, label, years[label])

    out("\nOVERALL January 2021 - October 2026 (descriptive pooling across periods; the models were refitted between "
        "periods, as each period's evaluation specified)")
    table(out, "2021-2026 pooled", rows)

    with open(TABLE, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    print(f"\nWritten to {OUTPUT} and {TABLE}")


if __name__ == "__main__":
    main()

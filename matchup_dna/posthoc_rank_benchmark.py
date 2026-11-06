"""POST-HOC descriptive benchmark, not part of the pre-registered Phase 4 evaluation.

    python -m matchup_dna.posthoc_rank_benchmark

On the 2,518 held-out matches (June-October 2026) already scored by `holdout --confirm`, compares the accuracy of
"the higher-ranked player wins" with the saved Phase 3 and Phase 4 predictions. Nothing is refitted or rescored:
it reads results/phase4/final/heldout_predictions.csv and the pre-match ranks on the provider rows behind each
match (the rank the models themselves used). Matches with a missing or tied rank are left out of the ranking
comparison, and the models are compared on exactly the same eligible matches.
"""
import csv

from matchup_dna import tennisdata as td
from matchup_dna import tennisismylife as tml
from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import Output
from matchup_dna.phase4_experiment import PROTOCOL_PATH

PREDICTIONS = RESULTS_DIR / "phase4" / "final" / "heldout_predictions.csv"
OUTPUT = RESULTS_DIR / "phase4" / "experiments" / "posthoc_rank_benchmark.txt"
MODELS = ("P3-refit", "P4-refit", "P3-original")


def number(value):
    value = (value or "").strip()
    return None if value == "" else int(float(value))


def winner_loser_ranks():
    """{match_id as in the predictions file: (winner rank, loser rank)} from the held-out provider rows."""
    found = {}
    for row in tml.load_tml(unseal_with=PROTOCOL_PATH):
        if "winner_id" in row:
            key = "|".join((row["tour"], f"TML-{row['tourney_id']}", row["match_num"], row["round"]))
            found[key] = (number(row["winner_rank"]), number(row["loser_rank"]))
    for row in td.load_provider(unseal_with=PROTOCOL_PATH):
        if row.get("winner_code") in ("1", "2") and td.is_main_draw(row):
            winner, loser = ("home", "away") if row["winner_code"] == "1" else ("away", "home")
            ranks = (number(row[f"{winner}_rank"]), number(row[f"{loser}_rank"]))
            prefix = f"{row['tour']}|TD-{td.edition_name(row['tournament'])}-"
            found[(prefix, row["match_id"], td.ROUNDS.get(row["round"]) or "unknown")] = ranks
    return found


def correct(probability, a_won):
    """1 if the model's favorite won, 0.5 for an exact 0.5, else 0 (the Phase 3 accuracy rule)."""
    if probability == 0.5:
        return 0.5
    return float((probability > 0.5) == a_won)


def main():
    out = Output()
    with open(PREDICTIONS, encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    ranks = winner_loser_ranks()
    td_ranks = {(k[0], k[1], k[2]): v for k, v in ranks.items() if isinstance(k, tuple)}

    eligible, reasons = [], {"missing rank": 0, "tied rank": 0, "no provider row found": 0}
    for row in rows:
        a_won = row["a_won"] == "1"
        found = ranks.get(row["match_id"])
        if found is None:
            tour, tourney, match_number, round_name = row["match_id"].split("|")
            prefix = f"{tour}|{tourney.rsplit('-', 1)[0]}-"
            found = td_ranks.get((prefix, match_number, round_name))
        if found is None:
            reasons["no provider row found"] += 1
            continue
        winner_rank, loser_rank = found
        if winner_rank is None or loser_rank is None:
            reasons["missing rank"] += 1
            continue
        if winner_rank == loser_rank:
            reasons["tied rank"] += 1
            continue
        eligible.append((row, winner_rank < loser_rank, a_won))

    out("POST-HOC DESCRIPTIVE BENCHMARK - not part of the pre-registered Phase 4 held-out evaluation.")
    out("Held-out June-October 2026 matches already scored by holdout --confirm; no model refitted or rescored.\n")
    out(f"Held-out matches: {len(rows):,}. Left out of the ranking comparison: "
        + ", ".join(f"{reason} {count:,}" for reason, count in reasons.items())
        + f". Eligible: {len(eligible):,}.")
    out("\nAccuracy on the eligible matches (identical set for every method)")
    out(f"   {'method':<40} {'tour':<5} {'matches':>8} {'correct':>9}  accuracy")
    results = {}
    for tour in ("ATP", "WTA", "Both"):
        subset = [e for e in eligible if tour == "Both" or e[0]["tour"] == tour]
        hits = {"Higher-ranked player": sum(higher_won for _, higher_won, _ in subset)}
        for model in MODELS:
            hits[model] = sum(correct(float(r[model]), a_won) for r, _, a_won in subset)
        results[tour] = (len(subset), hits)
        for method, count in hits.items():
            out(f"   {method:<40} {tour:<5} {len(subset):>8,} {count:>9,.1f}  {count / len(subset):.2%}")
    out("\nDifferences in accuracy, percentage points (eligible matches)")
    for tour, (n, hits) in results.items():
        base = hits["Higher-ranked player"] / n
        out(f"   {tour}: Phase 3 (refit) minus ranking {100 * (hits['P3-refit'] / n - base):+.2f}; Phase 4 minus ranking "
            f"{100 * (hits['P4-refit'] / n - base):+.2f}; Phase 4 minus Phase 3 {100 * (hits['P4-refit'] - hits['P3-refit']) / n:+.2f}")
    all_hits = {model: sum(correct(float(r[model]), r["a_won"] == "1") for r in rows) for model in MODELS}
    out(f"\nFor reference, all {len(rows):,} held-out matches: " + ", ".join(
        f"{model} {hits / len(rows):.2%}" for model, hits in all_hits.items()))
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    print(f"\nWritten to {OUTPUT}")


if __name__ == "__main__":
    main()

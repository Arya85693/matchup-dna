"""POST-HOC descriptive analysis, not pre-registered: where Phase 4 (and Phase 3) disagree with "the higher-ranked
player wins", which side was right?

    python -m matchup_dna.posthoc_rank_disagreement              (corrected held-out rows, erratum 1; primary)
    python -m matchup_dna.posthoc_rank_disagreement --original   (the original, affected 2,518 rows, for reference)

Reads the per-match tables written by posthoc_disagreement (results/phase4/experiments/posthoc_disagreement_matches
[_corrected].csv): saved P3-refit and P4-refit probabilities and the pre-match ranks the models used. Nothing is
refitted or rescored. Ranking-eligible matches have two known, different ranks. A model's pick is the player it
gives more than 0.5; an exact 0.5 is no pick and is counted separately. On matches where the model and the ranking
pick different players exactly one of them is right, so an exact two-sided sign test (McNemar's exact test) says
whether the split differs from 50/50. The corrected rows were examined after unblinding, so this is descriptive.
"""
import csv
import math
import sys
from collections import defaultdict

from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import Output

ORIGINAL = "--original" in sys.argv
SUFFIX = "" if ORIGINAL else "_corrected"
TABLE = RESULTS_DIR / "phase4" / "experiments" / f"posthoc_disagreement_matches{SUFFIX}.csv"
OUTPUT = RESULTS_DIR / "phase4" / "experiments" / f"posthoc_rank_disagreement{SUFFIX}.txt"
EXPECTED = {False: (2430, 1585, 1592, 1597), True: (2493, 1620, 1621, 1629)}  # eligible, rank, P3, P4 correct


def number(value):
    return None if value == "" else float(value)


def load():
    rows = []
    with open(TABLE, encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            a_rank, b_rank = number(row["a_rank"]), number(row["b_rank"])
            if a_rank is None or b_rank is None or a_rank == b_rank:
                continue
            a_won = row["a_won"] == "1"
            rows.append({**row, "a_won": a_won, "p3": float(row["p3"]), "p4": float(row["p4"]),
                         "elo_probability": float(row["elo_probability"]),
                         "rank_picks_a": a_rank < b_rank, "rank_ratio": max(a_rank, b_rank) / min(a_rank, b_rank),
                         "rank_right": (a_rank < b_rank) == a_won})
    return rows


def credit(p, a_won):
    return 0.5 if p == 0.5 else float((p > 0.5) == a_won)


def sign_test(wins, losses):
    """Exact two-sided binomial test of wins against losses at p = 0.5."""
    n, k = wins + losses, min(wins, losses)
    if n == 0:
        return float("nan")
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def wilson(successes, n):
    """95% Wilson interval for a proportion."""
    if n == 0:
        return float("nan"), float("nan")
    z, p = 1.96, successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def split(rows, model):
    """Matches where the model's pick and the ranking's pick differ (model's exact 0.5 excluded)."""
    agree, disagree, even = [], [], []
    for r in rows:
        p = r[model]
        if p == 0.5:
            even.append(r)
        elif (p > 0.5) == r["rank_picks_a"]:
            agree.append(r)
        else:
            disagree.append(r)
    return agree, disagree, even


def describe(out, rows, model, label):
    agree, disagree, even = split(rows, model)
    model_right = sum(not r["rank_right"] for r in disagree)  # exactly one side is right on a disagreement
    rank_right = len(disagree) - model_right
    low, high = wilson(model_right, len(disagree))
    agree_right = sum(r["rank_right"] for r in agree)
    out(f"\n{label} AGAINST THE HIGHER-RANKED PLAYER ({len(rows):,} ranking-eligible matches)")
    out(f"   Same pick: {len(agree):,} ({len(agree) / len(rows):.2%}); both right in {agree_right:,} "
        f"({agree_right / len(agree):.2%})")
    out(f"   Different pick: {len(disagree):,} ({len(disagree) / len(rows):.2%}); {label} right {model_right}, "
        f"ranking right {rank_right}; {label} share {model_right / len(disagree):.1%} (95% {low:.1%} to {high:.1%}); "
        f"net {model_right - rank_right:+d} picks; exact sign test p = {sign_test(model_right, rank_right):.3f}")
    if even:
        out(f"   {label} gave exactly 0.5 (no pick): {len(even)} match(es), counted as half a correct pick overall")
    confidence = [max(r[model], 1 - r[model]) for r in disagree]
    if disagree:
        mean_conf = sum(confidence) / len(confidence)
        out(f"   On the disagreements {label} gave its pick on average {mean_conf:.3f}; its pick won "
            f"{model_right / len(disagree):.3f} (calibration check: these should be close)")
    return {"agree": agree, "disagree": disagree, "model_right": model_right, "rank_right": rank_right}


def breakdown(out, title, disagree, key, order):
    groups = defaultdict(list)
    for r in disagree:
        groups[key(r)].append(r)
    out(f"   {title}")
    for name in order:
        subset = groups.get(name, [])
        if not subset:
            continue
        right = sum(not r["rank_right"] for r in subset)
        out(f"      {name:<34} {len(subset):>4}  model right {right:>3}, ranking right {len(subset) - right:>3}  "
            f"({right / len(subset):.0%}; sign test p {sign_test(right, len(subset) - right):.2f})"
            + ("  small" if len(subset) < 30 else ""))


def main():
    out = Output()
    rows = load()
    version = "ORIGINAL, AFFECTED 2,518-ROW" if ORIGINAL else "CORRECTED (ERRATUM 1, RETROSPECTIVE, POST-UNBLINDING)"
    out(f"POST-HOC DESCRIPTIVE ANALYSIS, not pre-registered: model picks against the higher-ranked player, {version}")
    out("held-out June-October 2026 predictions. Saved predictions only; nothing refitted. The ranking rule gives no")
    out("probabilities, so only winner picks are compared. Associations only.")
    found = (len(rows), sum(r["rank_right"] for r in rows), sum(credit(r["p3"], r["a_won"]) for r in rows),
             sum(credit(r["p4"], r["a_won"]) for r in rows))
    ok = found == EXPECTED[ORIGINAL]
    out(f"\nReproduction: {found[0]:,} eligible; correct picks ranking {found[1]:g}, Phase 3 {found[2]:g}, Phase 4 "
        f"{found[3]:g}; expected {EXPECTED[ORIGINAL]} -> {'reproduced' if ok else 'DIFFERS'}")
    if not ok:
        raise SystemExit("The table does not reproduce the ranking benchmark; stopping.")

    for model, label in (("p4", "PHASE 4"), ("p3", "PHASE 3")):
        result = describe(out, rows, model, label)
        disagree = result["disagree"]
        for tour in ("ATP", "WTA"):
            t = [r for r in disagree if r["tour"] == tour]
            right = sum(not r["rank_right"] for r in t)
            if t:
                out(f"   {tour}: {len(t)} disagreements; model right {right}, ranking right {len(t) - right} "
                    f"(sign test p {sign_test(right, len(t) - right):.2f})")
        if model != "p4":
            continue
        out("\n   Phase 4 disagreements, broken down (descriptive; overlapping slices chosen after the results)")
        breakdown(out, "How confident Phase 4 was in its own pick", disagree,
                  lambda r: "0.50-0.55" if max(r["p4"], 1 - r["p4"]) < 0.55 else
                  "0.55-0.60" if max(r["p4"], 1 - r["p4"]) < 0.60 else "0.60 and over",
                  ("0.50-0.55", "0.55-0.60", "0.60 and over"))
        breakdown(out, "How far apart the two ranks were (higher rank / lower rank)", disagree,
                  lambda r: "ratio under 1.5" if r["rank_ratio"] < 1.5 else "1.5-2" if r["rank_ratio"] < 2
                  else "2-4" if r["rank_ratio"] < 4 else "4 and over",
                  ("ratio under 1.5", "1.5-2", "2-4", "4 and over"))
        breakdown(out, "Does ordinary Elo side with Phase 4 or with the ranking?", disagree,
                  lambda r: "Elo sides with Phase 4" if (r["elo_probability"] > 0.5) == (r["p4"] > 0.5)
                  else "Elo sides with the ranking", ("Elo sides with Phase 4", "Elo sides with the ranking"))
        breakdown(out, "Surface", disagree, lambda r: r["surface"] or "unknown", ("Hard", "Clay", "Grass", "unknown"))

    p3_agree, p3_dis, _ = split(rows, "p3")
    p4_agree, p4_dis, _ = split(rows, "p4")
    only_p4 = {r["match_id"] for r in p4_dis} - {r["match_id"] for r in p3_dis}
    only_p3 = {r["match_id"] for r in p3_dis} - {r["match_id"] for r in p4_dis}
    out(f"\nOverlap: {len(p4_dis)} Phase 4 disagreements with the ranking, {len(p3_dis)} for Phase 3; "
        f"{len(only_p4)} only Phase 4's, {len(only_p3)} only Phase 3's.")
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    print(f"\nWritten to {OUTPUT}")


if __name__ == "__main__":
    main()

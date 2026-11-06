"""POST-HOC descriptive disagreement analysis of the June-October 2026 held-out matches. Not part of the
pre-registered Phase 4 evaluation, not a new independent test, and not used to choose or change anything.

    python -m matchup_dna.posthoc_disagreement              (reuses the match table if it exists)
    python -m matchup_dna.posthoc_disagreement --rebuild    (replays the match details again)
    python -m matchup_dna.posthoc_disagreement --corrected  (erratum 1: the corrected, post-unblinding rebuild's
                                                             predictions and version-2 rows; separate output files)

Compares the saved P3-refit and P4-refit predictions (results/phase4/final/heldout_predictions.csv), exactly as
written by holdout --confirm. No model is refitted, recalibrated, or rescored with new settings. Match details
(players, surface, level, round, Elo, ranks, serve and return estimates, statistics history) are not in the saved
file, so they are rebuilt by replaying the frozen held-out data pipeline (provider_period). That replay fits
nothing, and every saved match must come back with the same players and outcome or the script stops.

Accuracy rule (Phase 3): a pick is the player given more than 0.5; an exact 0.5 counts as half a correct pick.
Per-match log loss is -log(probability given to the actual winner); the difference is Phase 4 minus Phase 3, so
negative means Phase 4 did better.
"""
import csv
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict

import numpy as np

from matchup_dna.elo import RESULTS_DIR
from matchup_dna.evaluate import clustered_standard_error
from matchup_dna.experiment import Output
from matchup_dna.features import to_day

CORRECTED = "--corrected" in sys.argv
SUFFIX = "_corrected" if CORRECTED else ""
PREDICTIONS = RESULTS_DIR / "phase4" / ("corrected" if CORRECTED else "final") / "heldout_predictions.csv"
OUTPUT = RESULTS_DIR / "phase4" / "experiments" / f"posthoc_disagreement{SUFFIX}.txt"
TABLE = RESULTS_DIR / "phase4" / "experiments" / f"posthoc_disagreement_matches{SUFFIX}.csv"
PUBLISHED = {"P3-refit": (0.6148, 0.6511), "P4-refit": (0.6108, 0.6547)}  # held-out log loss, accuracy
PUBLISHED_RANK_ELIGIBLE = (2493, 1621, 1629)  # matches, Phase 3 correct, Phase 4 correct (post-hoc rank benchmark)
SMALL = 100  # groups with fewer matches are flagged as too small to read much into


def expected_scores():
    """The figures Part 1 must reproduce: the published ones, or the corrected rebuild's (erratum 1)."""
    if not CORRECTED:
        return PUBLISHED, PUBLISHED_RANK_ELIGIBLE
    summary = json.loads((RESULTS_DIR / "phase4" / "corrected" / "summary.json").read_text(encoding="utf-8"))
    scores = summary["corrected"]["scores"]
    ranking = summary["corrected"]["ranking"]
    return ({name: (round(scores[name]["log_loss"], 4), round(scores[name]["accuracy"], 4)) for name in PUBLISHED},
            (ranking["eligible"], ranking["P3_correct"], ranking["P4_correct"]))


def logit(p):
    return math.log(p / (1 - p))


def build_table():
    """One row per saved held-out match: the saved probabilities plus descriptive details from the replay."""
    from matchup_dna.phase4_experiment import HELD_OUT, PROTOCOL_PATH, history_matches, provider_period
    with open(PREDICTIONS, encoding="utf-8", newline="") as file:
        saved = list(csv.DictReader(file))
    # version 1 is the saved, original run; version 2 the corrected rebuild of erratum 1
    rows, _, _, _ = provider_period(*HELD_OUT, unseal_with=PROTOCOL_PATH, version=2 if CORRECTED else 1)
    rebuilt = {row["match_id"]: row for row in rows if row["tourney_date"] >= HELD_OUT[0]}
    missing = [s["match_id"] for s in saved if s["match_id"] not in rebuilt]
    if missing:
        raise SystemExit(f"{len(missing)} saved held-out matches were not rebuilt; stopping.")
    table = []
    for s in saved:
        row = rebuilt[s["match_id"]]
        if s["a_id"] != str(row["a_id"]) or int(s["a_won"]) != row["a_won"]:
            raise SystemExit(f"{s['match_id']}: the rebuilt players or outcome differ from the saved file; stopping.")
        edge = {}
        for stat in ("serve", "return"):
            a, b = row[f"a_{stat}_adjusted"], row[f"b_{stat}_adjusted"]
            edge[stat] = None if a is None or b is None else logit(a) - logit(b)
        table.append({
            "match_id": s["match_id"], "tourney_date": int(s["tourney_date"]), "tour": s["tour"],
            "tourney_level": row["tourney_level"], "surface": row["surface"], "round": row["round"],
            "best_of": row["best_of"], "a_name": row["a_name"], "b_name": row["b_name"], "a_won": int(s["a_won"]),
            "p3": float(s["P3-refit"]), "p4": float(s["P4-refit"]),
            "elo_diff": row["elo_diff"], "elo_probability": row["elo_probability"],
            "a_rank": row["a_rank"], "b_rank": row["b_rank"],
            "serve_edge": edge["serve"], "return_edge": edge["return"],
            "a_history": history_matches(row, "a"), "b_history": history_matches(row, "b"),
        })
    with open(TABLE, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    return table


def read_table():
    numbers = {"tourney_date", "a_won", "best_of"}
    floats = {"p3", "p4", "elo_diff", "elo_probability", "serve_edge", "return_edge", "a_history", "b_history"}
    found = []
    with open(TABLE, encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            for field in numbers | floats | {"a_rank", "b_rank"}:
                value = row[field]
                row[field] = None if value == "" else (float(value) if field in floats else int(float(value)))
            found.append(row)
    return found


def pick(p):
    return "A" if p > 0.5 else ("B" if p < 0.5 else "even")


def credit(p, a_won):
    """Correct-pick credit under the Phase 3 rule."""
    return 0.5 if p == 0.5 else float((p > 0.5) == bool(a_won))


def enrich(rows):
    for r in rows:
        y = r["a_won"]
        for m in ("p3", "p4"):
            r[f"{m}_pick"] = pick(r[m])
            r[f"{m}_correct"] = credit(r[m], y)
            r[f"{m}_winner_p"] = r[m] if y else 1 - r[m]
            r[f"{m}_ll"] = -math.log(r[f"{m}_winner_p"])
        r["d"] = r["p4_ll"] - r["p3_ll"]
        if "even" in (r["p3_pick"], r["p4_pick"]):
            r["agreement"] = "an exact 0.5"
        else:
            r["agreement"] = "agree" if r["p3_pick"] == r["p4_pick"] else "disagree"
        # who the Elo favourite is (the model-free reference used for orientation below)
        r["elo_fav_sign"] = 1 if r["elo_probability"] > 0.5 else -1
        if r["serve_edge"] is None or r["return_edge"] is None:
            r["sr_edge_for_elo_fav"] = None
        else:
            r["sr_edge_for_elo_fav"] = r["elo_fav_sign"] * (r["serve_edge"] + r["return_edge"])
        r["rank_eligible"] = r["a_rank"] is not None and r["b_rank"] is not None and r["a_rank"] != r["b_rank"]
    return rows


def mean_se(rows):
    d = [r["d"] for r in rows]
    if len(d) < 2 or len({r["tourney_date"] for r in rows}) < 2:  # one cluster: no clustered standard error
        return (float(np.mean(d)) if d else float("nan")), float("nan")
    return float(np.mean(d)), clustered_standard_error(d, [r["tourney_date"] for r in rows])


# ---------------------------------------------------------------- parts

def part1(out, rows):
    n = len(rows)
    published, rank_eligible = expected_scores()
    source = "corrected rebuild" if CORRECTED else "published"
    out("PART 1. Winner picks (all held-out matches with both predictions)")
    for m, name in (("p3", "P3-refit"), ("p4", "P4-refit")):
        acc = sum(r[f"{m}_correct"] for r in rows) / n
        ll = float(np.mean([r[f"{m}_ll"] for r in rows]))
        ok = round(ll, 4) == published[name][0] and round(acc, 4) == published[name][1]
        out(f"   {name}: {n:,} matches, accuracy {acc:.2%}, log loss {ll:.4f}; {source} {published[name][1]:.2%}, "
            f"{published[name][0]:.4f} -> {'reproduced' if ok else 'DIFFERS'}")
        if not ok:
            raise SystemExit(f"The saved predictions do not reproduce the {source} held-out scores; stopping.")
    eligible = [r for r in rows if r["rank_eligible"]]
    hits = (len(eligible), sum(r["p3_correct"] for r in eligible), sum(r["p4_correct"] for r in eligible))
    ok = hits == tuple(rank_eligible)
    out(f"   Ranking-eligible matches: {hits[0]:,}; Phase 3 correct {hits[1]:g}, Phase 4 correct {hits[2]:g}; {source} "
        f"{rank_eligible[0]:,}, {rank_eligible[1]:g}, {rank_eligible[2]:g} -> "
        f"{'reproduced' if ok else 'DIFFERS'}")
    if not ok:
        raise SystemExit("The ranking-eligible counts do not reproduce; stopping.")
    exact = {m: sum(r[m] == 0.5 for r in rows) for m in ("p3", "p4")}
    out(f"   Exact 0.5 predictions (as saved, 6 decimals): Phase 3 {exact['p3']}, Phase 4 {exact['p4']}")

    groups = defaultdict(list)
    for r in rows:
        groups[r["agreement"]].append(r)
    out(f"\n   {'subset':<16} {'matches':>8} {'share':>7}  {'P3 correct':>10} {'P4 correct':>10}  {'P3 acc':>7} {'P4 acc':>7}")
    for name in ("agree", "disagree", "an exact 0.5"):
        subset = groups.get(name, [])
        if not subset:
            out(f"   {name:<16} {0:>8}")
            continue
        c3, c4 = sum(r["p3_correct"] for r in subset), sum(r["p4_correct"] for r in subset)
        out(f"   {name:<16} {len(subset):>8,} {len(subset) / n:>7.2%}  {c3:>10,g} {c4:>10,g}  {c3 / len(subset):>7.2%} "
            f"{c4 / len(subset):>7.2%}")
    dis = groups.get("disagree", [])
    c3, c4 = sum(r["p3_correct"] for r in dis), sum(r["p4_correct"] for r in dis)
    out(f"   Disagreements: Phase 3 right {c3:g}, Phase 4 right {c4:g}; net {c4 - c3:+g} correct picks for Phase 4.")
    if dis:
        # exact two-sided sign test on the disagreements, descriptive only
        k, m = int(min(c3, c4)), int(c3 + c4)
        p = min(1.0, 2 * sum(math.comb(m, i) for i in range(k + 1)) / 2 ** m)
        out(f"   (Descriptive sign test on the {m} disagreements: two-sided p = {p:.2f}.)")
    for tour in ("ATP", "WTA"):
        t = [r for r in rows if r["tour"] == tour]
        td = [r for r in t if r["agreement"] == "disagree"]
        out(f"   {tour}: {len(td)} of {len(t):,} disagree ({len(td) / len(t):.1%}); Phase 3 right "
            f"{sum(r['p3_correct'] for r in td):g}, Phase 4 right {sum(r['p4_correct'] for r in td):g}")
    probs = [abs(r["p4"] - r["p3"]) for r in dis]
    if dis:
        out(f"   On disagreements both models sit near 0.5: median |P3 - 0.5| "
            f"{np.median([abs(r['p3'] - 0.5) for r in dis]):.3f}, median |P4 - 0.5| "
            f"{np.median([abs(r['p4'] - 0.5) for r in dis]):.3f}, median |P4 - P3| {np.median(probs):.3f}")
    return groups


def category(r):
    if r["agreement"] == "disagree":
        return "Disagree: Phase 4 right" if r["p4_correct"] == 1 else "Disagree: Phase 3 right"
    if r["agreement"] == "an exact 0.5":
        return "An exact 0.5"
    both_right = r["p3_correct"] == 1
    direction = "Phase 4 more confident" if (r["p4_winner_p"] > r["p3_winner_p"]) == both_right else "Phase 4 less confident"
    if r["p4"] == r["p3"]:
        direction = "identical"
    return f"Agree, both right: {direction}" if both_right else f"Agree, both wrong: {direction}"


CATEGORY_ORDER = ("Disagree: Phase 4 right", "Disagree: Phase 3 right",
                  "Agree, both right: Phase 4 more confident", "Agree, both right: Phase 4 less confident",
                  "Agree, both wrong: Phase 4 less confident", "Agree, both wrong: Phase 4 more confident",
                  "Agree, both right: identical", "Agree, both wrong: identical", "An exact 0.5")


def describe_match(r):
    winner = r["a_name"] if r["a_won"] else r["b_name"]
    names = {"A": r["a_name"], "B": r["b_name"], "even": "even"}
    return (f"{r['tourney_date']} {r['tour']} {r['surface'] or '?'} {r['tourney_level']} {r['round']}: "
            f"{r['a_name']} v {r['b_name']}; won by {winner}. P3 picked {names[r['p3_pick']]} "
            f"(P(A) {r['p3']:.3f}, winner {r['p3_winner_p']:.3f}); P4 picked {names[r['p4_pick']]} "
            f"(P(A) {r['p4']:.3f}, winner {r['p4_winner_p']:.3f}); difference {r['d']:+.4f}")


def part2(out, rows, groups):
    n = len(rows)
    total = sum(r["d"] for r in rows)
    mean, se = mean_se(rows)
    out("\nPART 2. Per-match log loss, Phase 4 minus Phase 3 (negative = Phase 4 better)")
    out(f"   All {n:,}: mean {mean:+.5f} (se clustered by tourney_date {se:.5f}); sum {total:+.3f}")
    for name in ("agree", "disagree", "an exact 0.5"):
        subset = groups.get(name, [])
        if subset:
            m, s = mean_se(subset)
            part = sum(r["d"] for r in subset)
            out(f"   {name:<12} {len(subset):>5,}: mean {m:+.5f} (se {s:.5f}); sum {part:+.3f}, "
                f"{part / total:.0%} of the total; contributes {part / n:+.5f} to the overall mean")
    better = sum(r["d"] < 0 for r in rows)
    same = sum(r["d"] == 0 for r in rows)
    out(f"   Phase 4 lower log loss on {better:,} matches ({better / n:.1%}); equal on {same}; higher on {n - better - same:,}")
    d = np.array([r["d"] for r in rows])
    qs = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
    out("   Distribution: " + ", ".join(f"{int(q * 100)}% {np.quantile(d, q):+.4f}" for q in qs)
        + f"; min {d.min():+.4f}, max {d.max():+.4f}, sd {d.std(ddof=1):.4f}")
    edges = (-math.inf, -0.2, -0.1, -0.05, -0.02, -0.005, 0.005, 0.02, 0.05, 0.1, 0.2, math.inf)
    out("   Histogram of the difference:")
    for lo, hi in zip(edges[:-1], edges[1:]):
        inside = d[(d >= lo) & (d < hi)]
        label = f"[{lo:+.3f}, {hi:+.3f})".replace("-inf", " -inf").replace("+inf", " +inf")
        out(f"      {label:<20} {len(inside):>5,}  sum {inside.sum():+7.3f}")

    out("\n   Where the total difference comes from")
    out(f"   {'category':<45} {'matches':>7} {'sum':>9} {'mean':>9} {'share of net':>12}")
    by = defaultdict(list)
    for r in rows:
        by[category(r)].append(r)
    for name in CATEGORY_ORDER:
        subset = by.get(name)
        if subset:
            part = sum(r["d"] for r in subset)
            out(f"   {name:<45} {len(subset):>7,} {part:>+9.3f} {part / len(subset):>+9.4f} {part / total:>12.0%}")
    out("   (Shares are of the net total; categories pull in both directions, so they can exceed 100% or be negative.)")

    order = sorted(rows, key=lambda r: r["d"])
    out("\n   20 matches where Phase 4 improved log loss the most")
    for i, r in enumerate(order[:20], 1):
        out(f"   {i:>2}. {describe_match(r)}")
    out("\n   20 matches where Phase 4 worsened log loss the most")
    for i, r in enumerate(reversed(order[-20:]), 1):
        out(f"   {i:>2}. {describe_match(r)}")
    top = sum(r["d"] for r in order[:20]) + sum(r["d"] for r in order[-20:])
    out(f"   The 40 extreme matches together sum to {top:+.3f}; the other {n - 40:,} to {total - top:+.3f}.")
    return by


def breakdown(out, title, rows, key, order=None):
    """Descriptive table: disagreement rate, accuracies, and the mean log-loss difference per group."""
    groups = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    names = order or sorted(groups, key=str)
    out(f"\n   {title}")
    out(f"   {'group':<30} {'matches':>7} {'disagree':>9} {'P3 acc':>7} {'P4 acc':>7} {'mean diff':>10} {'(se)':>8} "
        f"{'sum':>8}")
    for name in names:
        subset = groups.get(name)
        if not subset:
            continue
        n = len(subset)
        dis = sum(r["agreement"] == "disagree" for r in subset)
        m, s = mean_se(subset)
        flag = "  small" if n < SMALL else ""
        out(f"   {str(name):<30} {n:>7,} {dis / n:>9.1%} {sum(r['p3_correct'] for r in subset) / n:>7.1%} "
            f"{sum(r['p4_correct'] for r in subset) / n:>7.1%} {m:>+10.4f} {s:>8.4f} {sum(r['d'] for r in subset):>+8.3f}{flag}")


def bin_of(value, cuts, labels, missing="missing"):
    if value is None:
        return missing
    for cut, label in zip(cuts, labels):
        if value < cut:
            return label
    return labels[-1]


def part3(out, rows):
    out("\nPART 3. Which matches produce disagreements (descriptive; 'mean diff' is Phase 4 minus Phase 3 log loss,")
    out(f"se clustered by tourney_date; groups under {SMALL} matches are marked small)")
    breakdown(out, "Tour", rows, lambda r: r["tour"])
    breakdown(out, "Surface", rows, lambda r: r["surface"] or "unknown")
    elo_labels = ("Elo gap < 50", "50-100", "100-200", "200-300", "300+")
    breakdown(out, "Elo rating difference (absolute)", rows,
              lambda r: bin_of(abs(r["elo_diff"]), (50, 100, 200, 300, math.inf), elo_labels), elo_labels)
    fav_labels = ("Elo favourite < 55%", "55-60%", "60-70%", "70-80%", "80%+")
    breakdown(out, "Close match vs clear favourite (ordinary Elo probability of the favourite)", rows,
              lambda r: bin_of(max(r["elo_probability"], 1 - r["elo_probability"]), (0.55, 0.60, 0.70, 0.80, 1.01),
                               fav_labels), fav_labels)

    def rank_gap(r):
        if r["a_rank"] is None or r["b_rank"] is None:
            return "rank missing"
        if r["a_rank"] == r["b_rank"]:
            return "tied rank"
        ratio = abs(math.log(r["a_rank"] / r["b_rank"]))
        return bin_of(ratio, (math.log(1.5), math.log(2), math.log(4), math.inf),
                      ("rank ratio < 1.5", "1.5-2", "2-4", "4+"))
    breakdown(out, "Ranking difference (ratio of the two ranks)", rows, rank_gap,
              ("rank ratio < 1.5", "1.5-2", "2-4", "4+", "tied rank", "rank missing"))

    def elo_vs_rank(r):
        if not r["rank_eligible"]:
            return "rank missing or tied"
        return "Elo and rank agree on favourite" if (r["elo_probability"] > 0.5) == (r["a_rank"] < r["b_rank"]) \
            else "Elo and rank disagree"
    breakdown(out, "Do Elo and ranking name the same favourite?", rows, elo_vs_rank)

    known = [r["sr_edge_for_elo_fav"] for r in rows if r["sr_edge_for_elo_fav"] is not None]
    cuts = tuple(np.quantile(known, (0.2, 0.4, 0.6, 0.8))) + (math.inf,)
    sr_labels = ("Q1 most against Elo fav", "Q2", "Q3", "Q4", "Q5 most for Elo fav")
    out(f"\n   Serve-return edge = logit difference in opponent-adjusted serve estimates + the same for return,")
    out(f"   signed so positive favours the ordinary-Elo favourite. Quintile cut points: "
        + ", ".join(f"{c:+.3f}" for c in cuts[:-1]))
    breakdown(out, "Opponent-adjusted serve-return edge of the Elo favourite (quintiles)", rows,
              lambda r: bin_of(r["sr_edge_for_elo_fav"], cuts, sr_labels), sr_labels + ("missing",))

    def directions(r):
        if r["serve_edge"] is None or r["return_edge"] is None:
            return "missing"
        s, t = r["elo_fav_sign"] * r["serve_edge"], r["elo_fav_sign"] * r["return_edge"]
        if s >= 0 and t >= 0:
            return "serve and return both favour"
        if s < 0 and t < 0:
            return "serve and return both oppose"
        return "serve and return split"
    breakdown(out, "Serve and return edges relative to the Elo favourite", rows, directions)

    hist_labels = ("no statistics history", "under 10 matches", "10-30 matches", "over 30 matches")
    breakdown(out, "Statistics history of the less-observed player (matches' worth of service points)", rows,
              lambda r: "no statistics history" if min(r["a_history"], r["b_history"]) == 0 else bin_of(
                  min(r["a_history"], r["b_history"]), (10, 30, math.inf), hist_labels[1:]), hist_labels)
    breakdown(out, "Tournament level", rows, lambda r: r["tourney_level"])
    round_order = ("R128", "R64", "R32", "R16", "QF", "SF", "F", "RR", "BR", "ER")
    breakdown(out, "Round", rows, lambda r: r["round"], round_order + tuple(
        sorted({r["round"] for r in rows} - set(round_order))))
    breakdown(out, "Best of", rows, lambda r: f"best of {r['best_of']}")
    breakdown(out, "Month", rows, lambda r: r["tourney_date"] // 100)


def name_tokens(name):
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return {t for t in re.split(r"[^a-z]+", text) if len(t) > 1}


def cross_source_duplicates(rows):
    """{TennisData.app match_id: TML match_id} for TennisData.app rows that repeat a TML row: same tour, within 14
    days, same round (TennisData.app 'unknown' allowed), and each player sharing a name token with one TML player.
    Found while examining this analysis's largest per-match losses; the held-out build kept both copies because the
    two providers' players were resolved to different ids (see the report)."""
    tml_rows = [r for r in rows if "|TML-" in r["match_id"]]
    found = {}
    for t in (r for r in rows if "|TD-" in r["match_id"]):
        day = to_day(t["tourney_date"])
        a, b = name_tokens(t["a_name"]), name_tokens(t["b_name"])
        for m in tml_rows:
            if m["tour"] != t["tour"] or abs((to_day(m["tourney_date"]) - day).days) > 14:
                continue
            if t["round"] not in (m["round"], "unknown"):
                continue
            c, d = name_tokens(m["a_name"]), name_tokens(m["b_name"])
            if (a & c and b & d) or (a & d and b & c):
                found[t["match_id"]] = m["match_id"]
                break
    return found


def part0(out, rows):
    """Data-integrity finding and a descriptive sensitivity check. Does not replace the pre-registered result."""
    duplicates = cross_source_duplicates(rows)
    td_rows = [r for r in rows if "|TD-" in r["match_id"]]
    winners_agree = 0
    by_id = {r["match_id"]: r for r in rows}
    for td_id, tml_id in duplicates.items():
        t, m = by_id[td_id], by_id[tml_id]
        tw = t["a_name"] if t["a_won"] else t["b_name"]
        mw = m["a_name"] if m["a_won"] else m["b_name"]
        winners_agree += bool(name_tokens(tw) & name_tokens(mw))
    out("PART 0. Data-integrity finding (found during this analysis; nothing was changed)")
    out(f"   Held-out rows from TennisData.app: {len(td_rows)}; of these, {len(duplicates)} repeat a TML row (same tour,")
    out(f"   tournament week, round and players under different provider spellings); the two copies name the same winner")
    out(f"   in {winners_agree} of {len(duplicates)}. Those matches are counted twice in the saved held-out evaluation.")
    out("   Sensitivity, saved predictions only (NOT a corrected result: the duplicates also updated ratings and profiles")
    out("   twice and some carry a wrongly resolved player identity, which affects other matches' predictions too):")
    for label, subset in (("all saved rows (as published)", rows),
                          ("without the duplicate TennisData.app copies", [r for r in rows if r["match_id"] not in duplicates]),
                          ("the duplicate TennisData.app copies only", [r for r in rows if r["match_id"] in duplicates])):
        n = len(subset)
        if n == 0:
            out(f"   {label:<45} none")
            continue
        ll3 = float(np.mean([r["p3_ll"] for r in subset]))
        ll4 = float(np.mean([r["p4_ll"] for r in subset]))
        a3 = sum(r["p3_correct"] for r in subset) / n
        a4 = sum(r["p4_correct"] for r in subset) / n
        m, s = mean_se(subset)
        dis = sum(r["agreement"] == "disagree" for r in subset)
        out(f"   {label:<45} n {n:>5,}: P3 {ll3:.4f} / {a3:.2%}, P4 {ll4:.4f} / {a4:.2%}; gap {m:+.4f} (se {s:.4f}, "
            f"95% {m - 1.96 * s:+.4f} to {m + 1.96 * s:+.4f}); disagreements {dis}")
    out()
    return duplicates


def main():
    out = Output()
    rows = build_table() if "--rebuild" in sys.argv or not TABLE.exists() else read_table()
    rows = enrich(rows)
    out("POST-HOC DESCRIPTIVE ANALYSIS - not part of the pre-registered Phase 4 evaluation, not a new independent test,")
    out("and not used to choose or change any model. Saved P3-refit and P4-refit held-out predictions, June-October 2026.")
    out("Associations only: nothing here shows that serving, returning or any other characteristic causes an outcome.")
    if CORRECTED:
        out("ERRATUM 1 VERSION: predictions of the corrected, retrospective, post-unblinding rebuild (version-2 assembly).")
    out()
    part0(out, rows)
    out(f"Parts 1-3 use all {len(rows):,} saved rows of this version.\n")
    groups = part1(out, rows)
    part2(out, rows, groups)
    part3(out, rows)
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    print(f"\nWritten to {OUTPUT} and {TABLE}")


if __name__ == "__main__":
    main()

"""POST-HOC illustration for working paper 1 (big matches), not part of any frozen protocol: what happened next to the
players with the most extreme big-match records?

    python -m matchup_dna.posthoc_big_match_players

Uses exactly the version 1 definitions (matchup_dna.posthoc_big_match): the same matches, the same per-period
calibration and the same shrunk scores, so the players are the ones behind the period-split correlations in the
paper (at least 10 big matches in both 2012-2018 and 2019 - May 2026). For each tour, players are ranked by their
2012-2018 big-match score, and the TOP and BOTTOM players are listed with their big matches, wins, calibrated
expected wins and scores in both periods, plus their clutch scores. Group means show how far the extremes moved
back toward zero. Descriptive only: no test, no model change. Reads Sackmann's files to 25 May 2026 only.
"""
import json

import numpy as np

from matchup_dna import posthoc_big_match as v1
from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import Output
from matchup_dna.load import load_matches

OUTPUT = RESULTS_DIR / "phase4" / "experiments" / "posthoc_big_match_players.txt"
SUMMARY = RESULTS_DIR / "phase4" / "experiments" / "posthoc_big_match_players.json"
SHOWN = 5


def names_of(matches):
    names = {}
    for match in matches:
        for side in ("winner", "loser"):
            names[(match["tour"], match[f"{side}_id"])] = match[f"{side}_name"]
    return names


def period_scores(rows, probabilities):
    """{player: dict} with big matches, wins, expected wins, big-match score and clutch score for one period."""
    big = v1.player_stats(rows, probabilities, "big")
    regular = v1.player_stats(rows, probabilities, "regular")
    score, clutch = v1.scores(big, regular)
    return {player: {"big": int(entry[0]), "won": float(entry[1]), "expected": float(entry[2]),
                     "score": float(score[player]), "clutch": float(clutch[player])} for player, entry in big.items()}


def summarise(group, key, period):
    return float(np.mean([p[period][key] for p in group]))


def main():
    out = Output()
    matches = load_matches()
    rows = v1.match_rows(matches)
    names = names_of(matches)
    rows_1, rows_2 = v1.within(rows, v1.PERIOD_1), v1.within(rows, v1.PERIOD_2)
    p_1, _ = v1.calibrate(rows_1)
    p_2, _ = v1.calibrate(rows_2)

    out("POST-HOC illustration: the most extreme 2012-2018 big-match records, and what followed in 2019 - May 2026")
    out(f"Players with {v1.MIN_BIG}+ big matches in both periods; scores are shrunk residual per match "
        f"(sum / (n + {v1.SHRINK})) in win-probability points, each period with its own calibration.")
    out()
    summary = {"definitions": {"shown": SHOWN, "min_big": v1.MIN_BIG, "shrink": v1.SHRINK,
                               "period_1": v1.PERIOD_1, "period_2": v1.PERIOD_2}, "tours": {}}
    for tour in ("ATP", "WTA"):
        t1 = [(r, p) for r, p in zip(rows_1, p_1) if r["tour"] == tour]
        t2 = [(r, p) for r, p in zip(rows_2, p_2) if r["tour"] == tour]
        first = period_scores([r for r, _ in t1], [p for _, p in t1])
        second = period_scores([r for r, _ in t2], [p for _, p in t2])
        both = [pl for pl in first if pl in second and first[pl]["big"] >= v1.MIN_BIG and second[pl]["big"] >= v1.MIN_BIG]
        ranked = sorted(both, key=lambda pl: first[pl]["score"], reverse=True)
        players = [{"name": names[pl], "early": first[pl], "late": second[pl]} for pl in ranked]
        top, bottom = players[:SHOWN], players[-SHOWN:]
        # Every eligible player, ranked: the share of top-half players who stayed above zero, and so on.
        half = len(players) // 2
        upper, lower = players[:half], players[-half:]
        result = {
            "players": len(players), "top": top, "bottom": bottom,
            "means": {
                label: {key: {period: summarise(group, key, period) for period in ("early", "late")}
                        for key in ("score", "clutch")}
                for label, group in (("top", top), ("bottom", bottom), ("upper half", upper), ("lower half", lower))
            },
            "top_still_positive": int(sum(p["late"]["score"] > 0 for p in top)),
            "bottom_still_negative": int(sum(p["late"]["score"] < 0 for p in bottom)),
        }
        summary["tours"][tour] = result
        out(f"{tour}: {len(players)} players")
        out(f"   {'player':<24} {'2012-18 big':>11} {'won':>4} {'exp':>6} {'score':>6} {'clutch':>7}   "
            f"{'2019-26 big':>11} {'won':>4} {'exp':>6} {'score':>6} {'clutch':>7}")
        for heading, group in (("top", top), ("bottom", bottom)):
            out(f"   {heading}")
            for p in group:
                e, l = p["early"], p["late"]
                out(f"   {p['name']:<24} {e['big']:>11} {e['won']:>4.0f} {e['expected']:>6.1f} {v1.pp(e['score']):>6} "
                    f"{v1.pp(e['clutch']):>7}   {l['big']:>11} {l['won']:>4.0f} {l['expected']:>6.1f} "
                    f"{v1.pp(l['score']):>6} {v1.pp(l['clutch']):>7}")
        for label, means in result["means"].items():
            out(f"   mean of {label:<11} score {v1.pp(means['score']['early'])} -> {v1.pp(means['score']['late'])}; "
                f"clutch {v1.pp(means['clutch']['early'])} -> {v1.pp(means['clutch']['late'])}")
        out(f"   top {SHOWN} still above zero in 2019-26: {result['top_still_positive']}; "
            f"bottom {SHOWN} still below zero: {result['bottom_still_negative']}")
        out()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {OUTPUT} and {SUMMARY}")


if __name__ == "__main__":
    main()

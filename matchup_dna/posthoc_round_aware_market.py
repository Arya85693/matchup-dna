"""POST-HOC descriptive analysis, not part of the frozen Phase 5 protocol: Phase 4's round-aware model (R0)
against the opening market.

    python -m matchup_dna.posthoc_round_aware_market

Phase 5 compared the market with tournament-start probabilities, which use no result from the same tournament,
while the market sees every earlier round. R0 adds the earlier rounds of the same edition (Phase 4's round-aware
track), so it is the fairer model to put next to the market. R0's per-match predictions were not saved, so they are
reproduced by re-running the frozen fits on earlier matches only, exactly as Phase 4 specified:

    2021-2023            fitted on 2010-2020 later-round rows (Phase 4 development)
    Jan 2024 - May 2026  fitted on 2010-2023 later-round rows (Phase 4 retrospective check)
    Jun - Oct 2026       fitted on 2010 - May 2026 later-round rows (the corrected held-out rebuild, erratum 1)

Each reproduction must match its published score, or the script stops. R0 applies only to later-round matches (a
player has already played in the edition), so every comparison here is on that subset, with R0, the
tournament-start Phase 4 model and the market scored on identical matches. Run after the Phase 5 evaluation had
been seen: descriptive only.
"""
import json

import numpy as np

from matchup_dna import signals, uncertainty
from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import Output, match_log_loss, scores
from matchup_dna.phase5_dataset import load

OUTPUT = RESULTS_DIR / "phase5" / "experiments" / "posthoc_round_aware_market.txt"
PUBLISHED = {"validation R0 minus reference": -0.0054, "retrospective R0 log loss": 0.5994,
             "held-out R0 log loss": 0.5993}


def per_tour_fit(fit_rows, rows, groups, l2, reps):
    from matchup_dna.phase4_model import Phase4Logistic
    p = {}
    for tour in ("ATP", "WTA"):
        train = [r for r in fit_rows if r["tour"] == tour]
        target = [r for r in rows if r["tour"] == tour]
        if target:
            model = Phase4Logistic(tuple(groups), l2[tour], reps[tour]).fit(train)
            p.update(zip((r["match_id"] for r in target), model.predict(target)))
    return p


def reproduce(protocol):
    """{match_id: R0 probability} for 2021 - October 2026, with each period checked against Phase 4."""
    from matchup_dna.phase4_experiment import HELD_OUT, PROTOCOL_PATH, provider_period
    from matchup_dna.phase4_features import load_phase4
    from matchup_dna.model import labels
    ra = protocol["round_aware"]["R0"]
    reps = protocol["tournament_start"]["model"]["representations"]
    later = lambda rows: [r for r in rows if r["ra_later_round"]]
    found, checks = {}, {}

    train, validation = load_phase4("train"), load_phase4("validation")
    p = per_tour_fit(later(train), later(validation), ra["groups"], ra["l2"], reps)
    found.update(p)
    rows = later(validation)
    import csv
    with open(RESULTS_DIR / "phase4" / "experiments" / "posthoc_longrun_predictions_corrected.csv", encoding="utf-8") as f:
        reference = {r["match_id"]: float(r["Phase 4"]) for r in csv.DictReader(f)}
    y = labels(rows)
    gap = float((match_log_loss(np.array([p[r["match_id"]] for r in rows]), y)
                 - match_log_loss(np.array([reference[r["match_id"]] for r in rows]), y)).mean())
    checks["validation R0 minus reference"] = (round(gap, 4), len(rows))

    retrospective = later(load_phase4("retrospective", unseal_with=PROTOCOL_PATH))
    p = per_tour_fit(later(train + validation), retrospective, ra["groups"], ra["l2"], reps)
    found.update(p)
    checks["retrospective R0 log loss"] = (round(float(match_log_loss(
        np.array([p[r["match_id"]] for r in retrospective]), labels(retrospective)).mean()), 4), len(retrospective))

    rows, _, _, _ = provider_period(*HELD_OUT, unseal_with=PROTOCOL_PATH, version=2)
    fit_rows = later([r for r in rows if 20100101 <= r["tourney_date"] < HELD_OUT[0]])
    held = later([r for r in rows if r["tourney_date"] >= HELD_OUT[0]])
    p = per_tour_fit(fit_rows, held, ra["groups"], ra["l2"], reps)
    found.update(p)
    checks["held-out R0 log loss"] = (round(float(match_log_loss(
        np.array([p[r["match_id"]] for r in held]), labels(held)).mean()), 4), len(held))
    return found, checks


def compare(out, title, rows):
    y = np.array([r["a_won"] for r in rows], dtype=float)
    clusters = [r["tourney_date"] for r in rows]
    market = np.array([r["p_market"] for r in rows])
    out(f"\n{title}: {len(rows):,} later-round matches with opening prices (power method)")
    out(f"   {'forecast':<34} {'log loss':>9} {'Brier':>8} {'accuracy':>9}")
    found = {}
    for name, p in (("opening market", market), ("R0 (round-aware Phase 4)", np.array([r["R0"] for r in rows])),
                    ("Phase 4 (tournament start)", np.array([r["Phase 4"] for r in rows]))):
        s = scores(p, y)
        found[name] = s
        out(f"   {name:<34} {s['log_loss']:>9.4f} {s['brier']:>8.4f} {s['accuracy']:>9.2%}")
    for name, key in (("R0 minus market", "R0"), ("Phase 4 minus market", "Phase 4")):
        d = match_log_loss(np.array([r[key] for r in rows]), y) - match_log_loss(market, y)
        mean, se = uncertainty.clustered_mean(d, clusters)
        low, high, p = uncertainty.interval(mean, se)
        found[name] = {"gap": mean, "se": se, "low": low, "high": high, "p": p}
        out(f"   {name:<34} {mean:+.4f} (se {se:.4f}; {low:+.4f} to {high:+.4f}; p {p:.3g})")
    d = match_log_loss(np.array([r["R0"] for r in rows]), y) - match_log_loss(np.array([r["Phase 4"] for r in rows]), y)
    mean, se = uncertainty.clustered_mean(d, clusters)
    out(f"   {'R0 minus Phase 4 (value of earlier rounds)':<34} {mean:+.4f} (se {se:.4f})")
    found["R0 minus Phase 4"] = {"gap": mean, "se": se}
    b, se = signals.information_slope([r["R0"] for r in rows], market, y, clusters)
    low, high, p = uncertainty.interval(b, se)
    out(f"   R0 information slope b {b:+.3f} (se {se:.3f}; {low:+.3f} to {high:+.3f})")
    found["R0 slope"] = {"b": b, "se": se, "low": low, "high": high}
    return found


def main():
    from matchup_dna.phase4_experiment import PROTOCOL_PATH as PHASE4_PROTOCOL
    from matchup_dna.phase5_experiment import PROTOCOL_PATH, prepare
    out = Output()
    out("POST-HOC DESCRIPTIVE ANALYSIS (not in the frozen Phase 5 protocol; run after its evaluation): the round-aware")
    out("model R0 against the opening market, on later-round matches only.")
    protocol4 = json.loads(PHASE4_PROTOCOL.read_text(encoding="utf-8"))
    r0, checks = reproduce(protocol4)
    out("\nReproduction of Phase 4's published round-aware scores:")
    for key, (value, n) in checks.items():
        ok = value == PUBLISHED[key]
        out(f"   {key}: {value:+.4f} on {n:,} rows; published {PUBLISHED[key]:+.4f} -> {'reproduced' if ok else 'DIFFERS'}")
        if not ok:
            raise SystemExit("A reproduced R0 set does not match Phase 4's published score; stopping.")
    protocol5 = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    settings = {"margin_method": protocol5["margin_method"], "blend_weights": protocol5["blend_weights"]}
    summary = {}
    for split, title in (("development", "DEVELOPMENT 2021-2023"), ("evaluation", "EVALUATION January 2024 - October 2026")):
        rows = load(split, unseal_with=PROTOCOL_PATH) if split == "evaluation" else load(split)
        rows = [dict(r, R0=r0[r["match_id"]]) for r in prepare(rows, settings) if r["match_id"] in r0]
        summary[split] = compare(out, title, rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    OUTPUT.with_suffix(".json").write_text(json.dumps({"checks": checks, **summary}, indent=2, default=float),
                                           encoding="utf-8")
    print(f"\nWritten to {OUTPUT}")


if __name__ == "__main__":
    main()

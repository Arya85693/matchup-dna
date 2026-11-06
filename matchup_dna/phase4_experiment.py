"""Phase 4 experiments. Development commands read only training (2010-2020) and validation (2021-2023) rows.

    python -m matchup_dna.phase4_experiment profiles       tune serve-return profiles on 2010-2020 (no outcomes)
    python -m matchup_dna.phase4_experiment dataset        build results/phase4/{train,validation,retrospective}.csv
    python -m matchup_dna.phase4_experiment tournament     tournament-start track: forward selection, A-C and D-ts
    python -m matchup_dna.phase4_experiment gbm            LightGBM on the Phase 3 and the selected feature sets
    python -m matchup_dna.phase4_experiment round-aware    round-aware track: R0, D, E, and the conditional steps
    python -m matchup_dna.phase4_experiment rank-check     outcome-free effect of the held-out rank source

Every command writes results/phase4/experiments/<name>.txt and a manifest, and appends to experiments/phase4_log.md.
The Phase 3 log, protocol, and results are never written.
"""
import argparse
import datetime
import functools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import EXPERIMENTS_DIR, Output, git_commit, manifest

PHASE4_DIR = RESULTS_DIR / "phase4"
OUTPUT_DIR = PHASE4_DIR / "experiments"
LOG_PATH = EXPERIMENTS_DIR / "phase4_log.md"
PROFILE_SETTINGS = PHASE4_DIR / "profile_settings.json"
PROFILE_FIT_END = 20180101
PROFILE_SCORE = (20180101, 20210101)


def save(name, out, inputs, summary, extra=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{name}.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    record = manifest(name, inputs, extra)
    (OUTPUT_DIR / f"{name}_manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", encoding="utf-8") as log:
        if new:
            log.write("# Phase 4 experiment log\n\nOne entry per run, appended by `python -m matchup_dna.phase4_experiment`.\n")
        log.write(f"\n## {record['created']} · {name}\n\ncommit `{record['git_commit']}`\n\n")
        for line in summary:
            log.write(f"- {line}\n")


def sackmann_inputs():
    from matchup_dna.load import TOURS, match_files
    return [path for tour in TOURS for path in match_files(tour)]


# ---------------------------------------------------------------- profiles

def experiment_profiles():
    """Chooses half-life, prior strength, and raw or opponent-adjusted estimates per tour, by how well the
    profiles forecast each player's service points won in their next match (2018-2020), using history before
    each match only. Match winners play no part."""
    from matchup_dna.profiles import HALF_LIVES, PRIOR_MATCHES, ProfileEngine, averages, replay
    from matchup_dna.workload import load_matches_with_workload

    out = Output()
    matches = load_matches_with_workload()
    means = averages(matches)
    out("Profile tuning. Target: binomial loss per service point of the Barnett-Clarke forecast of each player's")
    out(f"service points won, scored on {PROFILE_SCORE[0]}-{PROFILE_SCORE[1]} matches with history from 1990. No match")
    out("winner is used. Tour averages (mu, attempts per match) from 2010-2020:")
    for tour, stats in sorted(means.items()):
        out(f"   {tour}: " + ", ".join(f"{stat} {mu:.4f} ({d:.1f})" for stat, (mu, d) in stats.items()))
    development = [m for m in matches if m["tourney_date"] < PROFILE_SCORE[1]]
    results = {}
    for half_life in HALF_LIVES:
        for prior in PRIOR_MATCHES:
            for tour in ("ATP", "WTA"):
                subset = [m for m in development if m["tour"] == tour]
                _, scores = replay(subset, ProfileEngine(means, half_life, prior), score_window=PROFILE_SCORE)
                results[(tour, half_life, prior)] = scores
                out(f"   {tour} half-life {str(half_life) + ' weeks' if half_life else 'none':<10} prior {prior:>2} matches: "
                    f"raw {scores[(tour, 'raw')]:.5f}  adjusted {scores[(tour, 'adjusted')]:.5f}  "
                    f"tour average {scores[(tour, 'tour average')]:.5f}")
    settings = {}
    for tour in ("ATP", "WTA"):
        options = [(scores[(tour, kind)], half_life, prior, kind) for (t, half_life, prior), scores in results.items()
                   if t == tour for kind in ("raw", "adjusted")]
        best = min(options, key=lambda option: option[0])
        best_raw = min((o for o in options if o[3] == "raw"), key=lambda option: option[0])
        settings[tour] = {"half_life": best[1], "prior_matches": best[2], "representation": best[3],
                          "loss": best[0], "best_raw_loss": best_raw[0]}
        average = results[(tour, best[1], best[2])][(tour, "tour average")]
        out(f"\n   {tour} chosen: half-life {best[1]}, prior {best[2]} matches, {best[3]} estimates; loss {best[0]:.5f} "
            f"per point (best raw {best_raw[0]:.5f}; tour average {average:.5f}, improvement {average - best[0]:.5f})")
    payload = {"means": {tour: {stat: list(v) for stat, v in stats.items()} for tour, stats in means.items()},
               "settings": settings, "created": datetime.date.today().isoformat(), "git_commit": git_commit()}
    PHASE4_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_SETTINGS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    save("profiles", out, sackmann_inputs(), [f"{tour}: {s}" for tour, s in settings.items()], extra={"settings": settings})


# ---------------------------------------------------------------- dataset

def experiment_dataset():
    from matchup_dna.experiment import PROTOCOL_PATH as PHASE3_PROTOCOL
    from matchup_dna.phase4_features import build_dataset, save_dataset

    out = Output()
    rows, report = build_dataset(PROFILE_SETTINGS, PHASE3_PROTOCOL)
    written = save_dataset(rows)
    out("Phase 4 dataset. Phase 3 rows rebuilt and checked against the frozen Phase 3 hashes:")
    for name, digest in report["phase3_hashes"].items():
        out(f"   {name}.csv sha256 {digest} (matches experiments/frozen_protocol.json)")
    out(f"TML backfill under the Phase 4 Data Audit precedence rules: {report['merge']}")
    for name, (path, count) in written.items():
        out(f"   {path.name:<20} {count:>7,} rows")
    eligible = [r for r in rows if r["period"] in ("train", "validation")]
    out(f"Round-aware sample (eligible, after the first round): "
        f"{sum(r['ra_later_round'] for r in eligible if r['period'] == 'train'):,} training rows, "
        f"{sum(r['ra_later_round'] for r in eligible if r['period'] == 'validation'):,} validation rows")
    inputs = sackmann_inputs() + [PROFILE_SETTINGS]
    save("dataset", out, inputs, [f"{name}: {count:,} rows" for name, (_, count) in written.items()],
         extra={"phase3_hashes": report["phase3_hashes"], "merge": report["merge"]})


# ---------------------------------------------------------------- shared evaluation helpers

def development():
    from matchup_dna.model import labels
    from matchup_dna.phase4_features import DATASET_DIR, FILES, load_phase4
    train, validation = load_phase4("train"), load_phase4("validation")
    return train, validation, labels(validation), [DATASET_DIR / FILES["train"], DATASET_DIR / FILES["validation"]]


def representations():
    settings = json.loads(PROFILE_SETTINGS.read_text(encoding="utf-8"))["settings"]
    return {tour: chosen["representation"] for tour, chosen in settings.items()}


def month_gap(p_new, p_old, y, rows):
    """Paired log-loss gap with standard errors clustered by calendar month instead of tournament date."""
    from matchup_dna.experiment import paired_gap
    import numpy as np
    return paired_gap(p_new, p_old, y, np.array([row["tourney_date"] // 100 for row in rows]))


def report_models(out, title, rows, y, models, baseline):
    """Score tables, paired gaps (date- and month-clustered), year and surface breakdowns, reliability, and
    calibration lines."""
    import numpy as np
    from matchup_dna.experiment import masks, print_breakdown, print_gaps, print_reliability, print_scores_table
    from matchup_dna.selection import calibration_line
    print_scores_table(out, title, rows, y, models)
    print_gaps(out, f"{title}: against {baseline}", rows, y, models, baseline)
    out(f"\n{title}: against {baseline}, standard errors clustered by calendar month")
    for name, p in models.items():
        if name != baseline:
            parts = []
            for tour, mask in masks(rows).items():
                gap, se = month_gap(p[mask], models[baseline][mask], y[mask], [r for r, m in zip(rows, mask) if m])
                parts.append(f"{tour} {gap:+.4f} (se {se:.4f})")
            out(f"   {name:<40} " + "  ".join(parts))
    print_breakdown(out, f"{title} by year", rows, y, models, lambda row: row["tourney_date"] // 10000)
    print_breakdown(out, f"{title} by surface", rows, y, models, lambda row: row["surface"] or "missing")
    print_reliability(out, title, rows, y, models)
    out(f"\n{title}: calibration line logit P(win) = a + b * logit(p) fitted on these rows (ideal a = 0, b = 1)")
    for name, p in models.items():
        parts = []
        for tour, mask in masks(rows).items():
            a, b = calibration_line(p[mask], y[mask])
            parts.append(f"{tour} a {a:+.3f} b {b:.3f}")
        out(f"   {name:<40} " + "  ".join(parts))


def subset_gaps(out, title, rows, y, models, baseline, subsets):
    import numpy as np
    from matchup_dna.experiment import print_gaps
    for label, keep in subsets:
        mask = np.array([bool(keep(row)) for row in rows], dtype=bool)
        if mask.sum() < 200:
            out(f"\n{title}, {label}: only {int(mask.sum())} matches, not reported")
            continue
        subset = [row for row, m in zip(rows, mask) if m]
        print_gaps(out, f"{title}, {label} ({int(mask.sum()):,} matches)", subset, y[mask],
                   {name: p[mask] for name, p in models.items()}, baseline)


@functools.lru_cache(maxsize=None)
def serve_points_per_match(tour):
    return json.loads(PROFILE_SETTINGS.read_text(encoding="utf-8"))["means"][tour]["serve"][1]


def history_matches(row, side):
    """A player's statistics history, in matches' worth of service points (tour average per match)."""
    return (row[f"{side}_serve_attempts"] or 0) / serve_points_per_match(row["tour"])


# ---------------------------------------------------------------- tournament-start track

TRACK_A = ("serve_return", "surface_serve_return", "recent_serve_return")
TRACK_B = ("serve_components", "break_points")
TRACK_C = ("product", "dominance_elo", "surface_interactions", "head_to_head")
TRACK_D = ("recent_workload",)
SELECTION_PATH = PHASE4_DIR / "selection.json"


def experiment_tournament():
    import numpy as np
    from matchup_dna.experiment import baselines, describe_keep, keep_rule
    from matchup_dna.phase4_model import PHASE3_GROUPS
    from matchup_dna.selection import fit_models, forward, model_state

    out = Output()
    train, validation, y, inputs = development()
    reps = representations()
    out("Tournament-start track. Forward selection in the pre-registered order, Phase 3 keep rule unchanged:")
    out("combined gap < -2 se, neither tour worse by > 1 se, at least 2 of 3 validation years better.")
    out(f"Serve and return estimates per tour: {reps}")
    base = model_state(train, validation, PHASE3_GROUPS, reps)
    out(f"\nBaseline: the Phase 3 groups {list(PHASE3_GROUPS)}, L2 re-chosen by the same inner split: {base['l2']} "
        f"(Phase 3 froze ATP 1000, WTA 100)")

    state, trail_a = forward(train, validation, y, base, TRACK_A, reps, out, "A. Ordinary serve-return groups")
    state, trail_b = forward(train, validation, y, state, TRACK_B, reps, out, "B. Serve components and break points")
    m2 = state if "serve_return" in state["groups"] else model_state(train, validation, state["groups"] + ("serve_return",), reps)
    if m2 is not state:
        out(f"\nM2 for interactions: the model so far plus serve_return (L2 {m2['l2']}), as pre-registered")
    after_c, trail_c = forward(train, validation, y, m2, TRACK_C, reps, out,
                               "C. Interactions, each tested against a model that already holds serve_return")
    selected = after_c if len(after_c["groups"]) > len(m2["groups"]) else state
    final, trail_d = forward(train, validation, y, selected, TRACK_D, reps, out, "D-ts. Workload in the previous 14 days")

    out("\nFinal candidate against the Phase 3 groups")
    verdict = keep_rule(validation, y, final["p"], base["p"])
    describe_keep(out, f"{list(final['groups'])}", verdict)
    if final["groups"] == base["groups"]:
        out("   No group was kept: the Phase 3 feature set stays the tournament-start model.")
    elif not verdict["passed"]:
        out("   The candidate does not pass against the Phase 3 groups: the Phase 3 feature set stays the model.")
    chosen = final if verdict["passed"] else base
    trails = trail_a + trail_b + trail_c + trail_d
    out(f"\nValidation comparisons made by this command: {len(trails) + 1} keep-rule decisions "
        f"(plus {sum(t[2] is not None for t in trails)} pairs of L2 sensitivity checks).")

    if len(chosen["groups"]) > len(base["groups"]):
        out("\nAblation: each added group removed from the chosen model")
        for group in chosen["groups"][len(PHASE3_GROUPS):]:
            fewer = tuple(g for g in chosen["groups"] if g != group)
            describe_keep(out, f"chosen - {group}", keep_rule(validation, y, model_state(
                train, validation, fewer, reps)["p"], chosen["p"]))

    models = baselines(train, validation)
    models["Phase 3 groups"] = base["p"]
    models["Phase 3 groups + serve_return"] = m2["p"] if "serve_return" in m2["groups"] else model_state(
        train, validation, base["groups"] + ("serve_return",), reps)["p"]
    models["Chosen model"] = chosen["p"]
    report_models(out, "Validation 2021-2023", validation, y, models, "Phase 3 groups")
    subset_gaps(out, "Validation", validation, y, models, "Phase 3 groups", [
        ("without overlap-flagged matches", lambda r: r["overlap_flag"] == 0),
        ("both players with statistics history", lambda r: r["a_serve_attempts"] and r["b_serve_attempts"]),
        ("less-observed player under 10 matches of statistics", lambda r: min(history_matches(r, "a"), history_matches(r, "b")) < 10),
        ("less-observed player 10-30 matches", lambda r: 10 <= min(history_matches(r, "a"), history_matches(r, "b")) <= 30),
        ("less-observed player over 30 matches", lambda r: min(history_matches(r, "a"), history_matches(r, "b")) > 30),
    ])
    if chosen is not base:
        out("\nCoefficients of the chosen model, fitted on 2010-2020 (feature units)")
        for tour, model in fit_models(train, chosen["groups"], chosen["l2"], reps).items():
            out(f"   {tour}: " + ", ".join(f"{k} {v:+.4f}" for k, v in model.unscaled_coefficients().items()))
    payload = {"groups": list(chosen["groups"]), "l2": chosen["l2"], "representations": reps,
               "baseline_l2": base["l2"], "passed_against_phase3": bool(verdict["passed"]),
               "candidate_groups": list(final["groups"]),
               "trail": [(g, o["passed"], o["gaps"]["Both"]) for g, o, _ in trails]}
    SELECTION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    save("tournament", out, inputs + [PROFILE_SETTINGS], [f"chosen groups {list(chosen['groups'])}, L2 {chosen['l2']}"] + [
        f"+{g}: passed={o['passed']}, combined {o['gaps']['Both'][0]:+.4f} (se {o['gaps']['Both'][1]:.4f})"
        for g, o, _ in trails], extra=payload)


def load_selection():
    if not SELECTION_PATH.exists():
        raise SystemExit("Run `python -m matchup_dna.phase4_experiment tournament` first.")
    found = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    found["groups"] = tuple(found["groups"])
    return found


# ---------------------------------------------------------------- LightGBM

GBM_PATH = PHASE4_DIR / "gbm.json"


def gbm_matrix(rows, groups, preprocessing):
    """Antisymmetric Phase 4 columns of the groups, then symmetric context. Returns (X, number antisymmetric)."""
    import numpy as np
    from matchup_dna.phase4_model import derived_columns, feature_names
    derived = derived_columns(rows, preprocessing)
    names = [name for name in feature_names(groups) if name != "surface_logit_x_experience"]
    antisymmetric = [derived[name] for name in names]
    a_matches = np.array([row["a_elo_matches"] for row in rows], dtype=float)
    b_matches = np.array([row["b_elo_matches"] for row in rows], dtype=float)
    symmetric = [np.log1p(np.minimum(a_matches, b_matches)),
                 np.array([row["best_of"] == 5 for row in rows], dtype=float),
                 np.array([row["surface"] == "Clay" for row in rows], dtype=float),
                 np.array([row["surface"] == "Grass" for row in rows], dtype=float)]
    return np.column_stack(antisymmetric + symmetric), len(antisymmetric)


def gbm_fit(rows, groups, representation, leaves, trees=None, early_rows=None):
    """Phase 3's LightGBM procedure on Phase 4 columns: both orderings of every match, the same constants."""
    import lightgbm
    import numpy as np
    from matchup_dna.experiment import GBM_EARLY_STOP, GBM_LEARNING_RATE, GBM_MAX_TREES, GBM_MIN_CHILD, flipped
    from matchup_dna.model import labels
    from matchup_dna.phase4_model import fit_preprocessing
    preprocessing = fit_preprocessing(rows, representation)
    X, k = gbm_matrix(rows, groups, preprocessing)
    y = labels(rows)
    params = {"objective": "binary", "learning_rate": GBM_LEARNING_RATE, "num_leaves": leaves,
              "min_child_samples": GBM_MIN_CHILD, "verbose": -1, "seed": 0, "deterministic": True,
              "force_row_wise": True, "num_threads": 1}
    data = lightgbm.Dataset(np.vstack([X, flipped(X, k)]), np.concatenate([y, 1 - y]))
    if early_rows is not None:
        Xe, _ = gbm_matrix(early_rows, groups, preprocessing)
        ye = labels(early_rows)
        valid = lightgbm.Dataset(np.vstack([Xe, flipped(Xe, k)]), np.concatenate([ye, 1 - ye]), reference=data)
        booster = lightgbm.train(params, data, GBM_MAX_TREES, valid_sets=[valid],
                                 callbacks=[lightgbm.early_stopping(GBM_EARLY_STOP, verbose=False)])
        return booster, preprocessing, k
    return lightgbm.train(params, data, trees), preprocessing, k


def gbm_predict(model, rows, groups):
    from matchup_dna.experiment import flipped
    booster, preprocessing, k = model
    X, _ = gbm_matrix(rows, groups, preprocessing)
    return 0.5 * (booster.predict(X) + 1 - booster.predict(flipped(X, k)))


def gbm_tune(rows, groups, representation):
    from matchup_dna.experiment import GBM_INNER_START, GBM_LEAVES
    from matchup_dna.model import labels, mean_log_loss
    early = [row for row in rows if row["tourney_date"] < GBM_INNER_START]
    late = [row for row in rows if row["tourney_date"] >= GBM_INNER_START]
    results = {}
    for leaves in GBM_LEAVES:
        model = gbm_fit(early, groups, representation, leaves, early_rows=late)
        results[leaves] = (mean_log_loss(gbm_predict(model, late, groups), labels(late)), model[0].best_iteration)
    leaves = min(results, key=lambda key: results[key][0])
    return {"leaves": leaves, "trees": results[leaves][1]}, results


def gbm_model(groups, settings, reps):
    def fit_predict(fit_rows, target_rows):
        tour = fit_rows[0]["tour"]
        chosen = settings[tour]
        return gbm_predict(gbm_fit(fit_rows, groups, reps[tour], chosen["leaves"], chosen["trees"]), target_rows, groups)
    return fit_predict


def experiment_gbm():
    from matchup_dna.experiment import describe_keep, keep_rule, per_tour, print_gaps, print_scores_table, tour_rows
    from matchup_dna.phase4_model import PHASE3_GROUPS

    out = Output()
    train, validation, y, inputs = development()
    reps, selection = representations(), load_selection()
    chosen = selection["groups"]
    out("LightGBM, trained on both orderings of each match. Leaves and trees chosen by the same inner split for")
    out(f"the Phase 3 feature set and for the chosen tournament-start set {list(chosen)}, plus symmetric context.")
    settings, predictions = {}, {}
    for label, groups in (("Phase 3 features", PHASE3_GROUPS), ("chosen features", chosen)):
        settings[label] = {}
        for tour in ("ATP", "WTA"):
            settings[label][tour], results = gbm_tune(tour_rows(train, tour), groups, reps[tour])
            out(f"   {label}, {tour}: " + ", ".join(f"{leaves} leaves {loss:.4f} at {trees} trees"
                                                   for leaves, (loss, trees) in results.items())
                + f" -> {settings[label][tour]}")
        predictions[f"LightGBM, {label}"] = per_tour(train, validation, gbm_model(groups, settings[label], reps))
    from matchup_dna.selection import logistic
    predictions["Logistic, chosen"] = per_tour(train, validation, logistic(chosen, selection["l2"], reps))
    print_scores_table(out, "Validation 2021-2023", validation, y, predictions)
    print_gaps(out, "Against logistic, chosen", validation, y, predictions, "Logistic, chosen")
    out("\nKeep rule")
    against_phase3 = keep_rule(validation, y, predictions["LightGBM, chosen features"], predictions["LightGBM, Phase 3 features"])
    describe_keep(out, "LightGBM chosen vs LightGBM Phase 3 features", against_phase3)
    against_logistic = keep_rule(validation, y, predictions["LightGBM, chosen features"], predictions["Logistic, chosen"])
    describe_keep(out, "LightGBM chosen vs logistic chosen", against_logistic)
    payload = {"settings": settings["chosen features"], "phase3_feature_settings": settings["Phase 3 features"],
               "passed_against_logistic": bool(against_logistic["passed"]),
               "passed_against_phase3_features": bool(against_phase3["passed"])}
    GBM_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    save("gbm", out, inputs + [SELECTION_PATH], [
        f"LightGBM chosen vs logistic chosen: passed={against_logistic['passed']}, combined "
        f"{against_logistic['gaps']['Both'][0]:+.4f} (se {against_logistic['gaps']['Both'][1]:.4f})",
        f"LightGBM chosen vs LightGBM Phase 3 features: passed={against_phase3['passed']}, combined "
        f"{against_phase3['gaps']['Both'][0]:+.4f} (se {against_phase3['gaps']['Both'][1]:.4f})"], extra=payload)


# ---------------------------------------------------------------- round-aware track

ROUND_AWARE_PATH = PHASE4_DIR / "round_aware.json"


def round_aware_sample(rows):
    return [row for row in rows if row["ra_later_round"]]


def experiment_round_aware():
    import numpy as np
    from matchup_dna.experiment import describe_keep, keep_rule, per_tour, print_breakdown
    from matchup_dna.model import labels
    from matchup_dna.selection import cross_l2, logistic, model_state

    out = Output()
    train, validation, _, inputs = development()
    reps, selection = representations(), load_selection()
    chosen = selection["groups"]
    fit_rows, rows = round_aware_sample(train), round_aware_sample(validation)
    y = labels(rows)
    out("Round-aware track. Sample: eligible matches after the edition's first round (Phase 4 Data Audit A7):")
    out(f"{len(fit_rows):,} training rows, {len(rows):,} validation rows. Every model below uses exactly these rows.")
    reference = per_tour(train, rows, logistic(chosen, selection["l2"], reps))
    r0 = model_state(fit_rows, rows, chosen + ("ra_controls",), reps)
    out(f"\nReference: the chosen tournament-start model {list(chosen)}, fitted on all training rows; it uses only")
    out("information from the tournament's start. R0 adds the round-aware Elo shifts and earlier-round dominance.")
    value_of_results = keep_rule(rows, y, r0["p"], reference)
    describe_keep(out, f"R0 vs reference (L2 {r0['l2']}), the value of knowing earlier results", value_of_results)

    def test(label, groups, against):
        state = model_state(fit_rows, rows, groups, reps)
        outcome = keep_rule(rows, y, state["p"], against["p"])
        describe_keep(out, f"{label} (L2 {state['l2']})", outcome)
        if outcome["passed"]:
            first, second = cross_l2(fit_rows, rows, y, against, state, reps)
            out(f"      sensitivity: at baseline L2 {first[0]:+.4f} (se {first[1]:.4f}); against baseline at "
                f"candidate L2 {second[0]:+.4f} (se {second[1]:.4f})")
        return state, outcome

    out("\nPre-registered tests, each against R0 unless stated")
    d, d_outcome = test("D: R0 + games in earlier rounds", r0["groups"] + ("ra_workload",), r0)
    e, e_outcome = test("E: R0 + route difficulty", r0["groups"] + ("ra_route",), r0)
    decisions = 3
    kept = r0
    if d_outcome["passed"] and e_outcome["passed"]:
        better = d if np.mean(np.log(np.where(y == 1, d["p"], 1 - d["p"]))) > np.mean(
            np.log(np.where(y == 1, e["p"], 1 - e["p"]))) else e
        de, de_outcome = test("D + E against the better single model", r0["groups"] + ("ra_workload", "ra_route"), better)
        decisions += 1
        kept = de if de_outcome["passed"] else better
        if de_outcome["passed"]:
            f, f_outcome = test("F: + workload x route", de["groups"] + ("ra_workload_route",), de)
            decisions += 1
            kept = f if f_outcome["passed"] else de
    elif d_outcome["passed"]:
        kept = d
    elif e_outcome["passed"]:
        kept = e
    else:
        out("   Neither D nor E passed, so D + E and F are not run, as pre-registered.")
    out(f"\nRound-aware model kept: {list(kept['groups'])}. Validation comparisons in this track: {decisions} "
        f"(R0 vs reference, D, E{', D + E' if decisions > 3 else ''}{', F' if decisions > 4 else ''}).")

    out("\nDiagnostics (reported only, never used to choose): substitutes for the games measure, and the strongest "
        "opponent beaten")
    diagnostics = {}
    for label, group in (("points instead of games", "ra_points_diagnostic"),
                         ("minutes instead of games", "ra_minutes_diagnostic"),
                         ("strongest opponent beaten", "ra_max_opponent_diagnostic")):
        state = model_state(fit_rows, rows, r0["groups"] + (group,), reps)
        diagnostics[label] = state["p"]
        describe_keep(out, f"diagnostic: R0 + {label}", keep_rule(rows, y, state["p"], r0["p"]))

    models = {"Reference (tournament start)": reference, "R0": r0["p"], "D": d["p"], "E": e["p"], "Kept": kept["p"]}
    report_models(out, "Round-aware validation", rows, y, models, "R0")
    print_breakdown(out, "Round-aware validation by round", rows, y, models, lambda row: row["round"])
    print_breakdown(out, "Round-aware validation by best-of", rows, y, models, lambda row: row["best_of"])
    subset_gaps(out, "Round-aware validation", rows, y, models, "R0", [
        ("Grand Slams", lambda r: r["tourney_level"] == "G"),
        ("without overlap-flagged matches", lambda r: r["overlap_flag"] == 0),
        ("without qualifiers or lucky losers", lambda r: not r["a_qualifier"] and not r["b_qualifier"]),
        ("quarterfinals and later", lambda r: r["round"] in ("QF", "SF", "F")),
    ])
    payload = {"kept_groups": list(kept["groups"]), "l2": kept["l2"], "r0_groups": list(r0["groups"]), "r0_l2": r0["l2"],
               "reference_groups": list(chosen), "decisions": decisions,
               "passed": {"R0 vs reference": bool(value_of_results["passed"]), "D": bool(d_outcome["passed"]),
                          "E": bool(e_outcome["passed"])},
               "gaps": {"R0 vs reference": value_of_results["gaps"]["Both"], "D": d_outcome["gaps"]["Both"],
                        "E": e_outcome["gaps"]["Both"]}, "validation_rows": len(rows)}
    ROUND_AWARE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    save("round-aware", out, inputs + [SELECTION_PATH], [
        f"R0 vs reference: passed={value_of_results['passed']}, combined {value_of_results['gaps']['Both'][0]:+.4f} "
        f"(se {value_of_results['gaps']['Both'][1]:.4f})",
        f"D: passed={d_outcome['passed']}, combined {d_outcome['gaps']['Both'][0]:+.4f} (se {d_outcome['gaps']['Both'][1]:.4f})",
        f"E: passed={e_outcome['passed']}, combined {e_outcome['gaps']['Both'][0]:+.4f} (se {e_outcome['gaps']['Both'][1]:.4f})",
        f"kept {list(kept['groups'])}"], extra=payload)


# ---------------------------------------------------------------- building a period from the providers

def provider_period(start, end, unseal_with=None, version=2):
    """Sackmann before `start` plus provider matches for editions in [start, end), every Phase 4 column built by
    the development code. Returns (rows, provider keys, report, Sackmann matches). version selects the provider
    assembly (heldout.assemble): 1 is the original, affected one the frozen commands ran; 2 is the correction of
    erratum 1."""
    from matchup_dna import heldout
    from matchup_dna import tennisdata as td
    from matchup_dna import tennisismylife as tml
    from matchup_dna.audit_tennisdata import sackmann_overlap
    from matchup_dna.crosswalk import load_player_names
    from matchup_dna.features import build_rows
    from matchup_dna.merge import combine
    from matchup_dna.phase4_features import augment, backfilled_matches

    sackmann, merge_report = backfilled_matches()
    overlap, names = sackmann_overlap(), load_player_names()
    tml_links, td_links = heldout.crosswalks(overlap, names)
    excluded = heldout.excluded_tournaments(overlap, names)
    tml_rows = tml.load_tml(unseal_with=unseal_with)
    td_rows = td.load_provider(unseal_with=unseal_with)
    window = [r for r in tml_rows if not r["sealed"] or unseal_with is not None]
    td_window = [r for r in td_rows if not r["sealed"] or unseal_with is not None]
    added, keys, report = heldout.assemble(window, td_window, sackmann, names, tml_links, td_links, excluded,
                                           start, end, heldout.snapshot_day(), version=version)
    history = [m for m in sackmann if m["tourney_date"] < start]
    # Rule 1 of the precedence: a match Sackmann already holds is never added again. An edition that starts just
    # after `start` can repeat a Sackmann edition dated just before it, so the same pair in the same round within
    # 14 days of a Sackmann match is dropped and counted.
    from matchup_dna.workload import to_day
    recent = defaultdict(list)
    for m in history:
        if m["tourney_date"] >= start - 10000:
            recent[(m["tour"], frozenset((m["winner_id"], m["loser_id"])), m["round"])].append(m["tourney_date"])
    kept = []
    for m in added:
        dates = recent.get((m["tour"], frozenset((m["winner_id"], m["loser_id"])), m["round"]), ())
        if any(abs((to_day(m["tourney_date"]) - to_day(d)).days) <= 14 for d in dates):
            report["provider matches dropped: already in Sackmann"] = report.get(
                "provider matches dropped: already in Sackmann", 0) + 1
        else:
            kept.append(m)
    matches, merge = combine(history, [(m, None, None) for m in kept], last_sackmann_week=start - 1)
    rows = augment(build_rows(matches), matches, PROFILE_SETTINGS)
    report.update({"excluded tournament names": excluded, "merge": merge})
    return rows, keys, report, sackmann


def fit_final_models(fit_rows, selection, reps, round_aware_choice):
    """The pre-registered models, refitted on fit_rows with L2 held at the development values."""
    from matchup_dna.experiment import tour_rows
    from matchup_dna.model import LogisticModel
    from matchup_dna.phase4_model import PHASE3_GROUPS, Phase4Logistic
    phase3_l2 = {"ATP": 1000.0, "WTA": 100.0}
    models = {}
    for tour in ("ATP", "WTA"):
        rows = tour_rows(fit_rows, tour)
        ra_rows = [r for r in rows if r["ra_later_round"]]
        models[tour] = {
            "P3-refit": LogisticModel(PHASE3_GROUPS, phase3_l2[tour]).fit(rows),
            "P4-refit": Phase4Logistic(selection["groups"], selection["l2"][tour], reps[tour]).fit(rows),
            "R0": Phase4Logistic(tuple(round_aware_choice["r0_groups"]), round_aware_choice["r0_l2"][tour], reps[tour]).fit(ra_rows),
            "RA-kept": Phase4Logistic(tuple(round_aware_choice["kept_groups"]), round_aware_choice["l2"][tour], reps[tour]).fit(ra_rows),
        }
    return models


def predict(models, rows, name):
    import numpy as np
    p = np.empty(len(rows))
    for tour in ("ATP", "WTA"):
        index = [i for i, row in enumerate(rows) if row["tour"] == tour]
        if index:
            p[index] = models[tour][name].predict([rows[i] for i in index])
    return p


# ---------------------------------------------------------------- rehearsal (no outcomes)

REHEARSAL = (20260112, 20260518)


def experiment_rehearse():
    """Runs the held-out pipeline on January to mid-May 2026, where the provider rows are open and Sackmann has
    the same matches, and compares provider-built probabilities with Sackmann-built ones. No win/loss outcome
    of these matches is scored. The same comparison with only the ranks swapped measures the rank-source effect."""
    import numpy as np
    from matchup_dna.features import build_rows
    from matchup_dna.phase4_features import augment, load_phase4

    out = Output()
    selection, reps = load_selection(), representations()
    round_choice = json.loads(ROUND_AWARE_PATH.read_text(encoding="utf-8"))
    rows, keys, report, sackmann = provider_period(*REHEARSAL, version=1)  # as run before the freeze
    out(f"Rehearsal of the held-out pipeline on editions starting {REHEARSAL[0]}-{REHEARSAL[1]} (open rows).")
    for key, value in report.items():
        out(f"   {key}: {value}")
    fit_rows = load_phase4("train") + load_phase4("validation")
    models = fit_final_models(fit_rows, selection, reps, round_choice)
    provider_rows = [r for r in rows if r["tourney_date"] >= REHEARSAL[0]]
    sackmann_rows = [r for r in augment(build_rows(sackmann), sackmann, PROFILE_SETTINGS)
                     if REHEARSAL[0] <= r["tourney_date"] < REHEARSAL[1]]

    def index(table):
        found = defaultdict(list)
        for row in table:
            found[(row["tour"], frozenset((row["a_id"], row["b_id"])), row["round"])].append(row)
        return found

    sackmann_index = index(sackmann_rows)
    pairs = []
    for row in provider_rows:
        candidates = [s for s in sackmann_index.get((row["tour"], frozenset((row["a_id"], row["b_id"])), row["round"]), ())
                      if abs(s["tourney_date"] - row["tourney_date"]) <= 7]
        if len(candidates) == 1:
            pairs.append((row, candidates[0]))
    out(f"\nProvider-built rated matches: {len(provider_rows):,}; Sackmann rated matches in the window: "
        f"{len(sackmann_rows):,}; matched one-to-one by Sackmann ids, round, and date: {len(pairs):,}")

    def oriented(p, provider, sackmann_row):
        return p if provider["a_id"] == sackmann_row["a_id"] else 1 - p

    for name in ("P3-refit", "P4-refit"):
        p_provider = predict(models, [p for p, _ in pairs], name)
        p_sackmann = predict(models, [s for _, s in pairs], name)
        gap = np.abs(np.array([oriented(a, p, s) for a, (p, s) in zip(p_provider, pairs)]) - p_sackmann)
        out(f"   {name}: |provider - Sackmann probability| mean {gap.mean():.4f}, median {np.median(gap):.4f}, "
            f"90th percentile {np.quantile(gap, 0.9):.4f}, over 0.05 in {np.mean(gap > 0.05):.1%}")
    for field in ("elo_diff", "a_serve_adjusted", "a_rank", "a_days_since"):
        values = [(p[field], s[field] if p["a_id"] == s["a_id"] else (-s[field] if field.endswith("diff") else s[field.replace("a_", "b_")]))
                  for p, s in pairs if p[field] is not None and s[field] is not None]
        equal = np.mean([abs(a - b) < 1e-6 for a, b in values]) if values else float("nan")
        out(f"   {field}: identical in {equal:.1%} of {len(values):,} matched rows")

    out("\nRank-source check: Sackmann-built rows with each player's rank replaced by the provider's rank on the")
    out("same match, everything else unchanged")
    swapped = []
    for provider, sackmann_row in pairs:
        copy = dict(sackmann_row)
        same = provider["a_id"] == sackmann_row["a_id"]
        copy["a_rank"] = provider["a_rank"] if same else provider["b_rank"]
        copy["b_rank"] = provider["b_rank"] if same else provider["a_rank"]
        swapped.append(copy)
    for name in ("P3-refit", "P4-refit"):
        gap = np.abs(predict(models, swapped, name) - predict(models, [s for _, s in pairs], name))
        out(f"   {name}: mean {gap.mean():.4f}, 90th percentile {np.quantile(gap, 0.9):.4f}, over 0.02 in {np.mean(gap > 0.02):.1%}")
    save("rehearse", out, [PROFILE_SETTINGS, SELECTION_PATH, ROUND_AWARE_PATH],
         [f"{len(pairs)} rehearsal matches compared; see results/phase4/experiments/rehearse.txt"])


# ---------------------------------------------------------------- freeze, retrospective, held-out

PROTOCOL_PATH = EXPERIMENTS_DIR / "phase4_frozen_protocol.json"
FINAL_DIR = PHASE4_DIR / "final"
RETROSPECTIVE_DIR = PHASE4_DIR / "retrospective"
HELD_OUT = (20260601, 20261105)
EXPECTED_HELD_OUT = {"tournament-start": 2500, "round-aware": 1300}


def minimum_detectable(se, validation_rows, held_out_rows):
    """The smallest true gain the held-out period would detect with 80% power at the 5% level (two-sided),
    scaling the validation standard error by the square root of the sample sizes: 2.8 standard errors."""
    scaled = se * (validation_rows / held_out_rows) ** 0.5
    return {"validation_se": se, "held_out_se": scaled, "minimum_detectable_gain": 2.8 * scaled}


CODE_PATHS = ("matchup_dna", "explain.py", "compare.py", "requirements.txt", "tests")


def head_commit():
    import subprocess
    from matchup_dna.experiment import ROOT
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def uncommitted_code():
    """Tracked or untracked changes under CODE_PATHS, as `git status --porcelain` lines."""
    import subprocess
    from matchup_dna.experiment import ROOT
    found = subprocess.run(["git", "status", "--porcelain", "--", *CODE_PATHS], cwd=ROOT, capture_output=True, text=True)
    return [line for line in found.stdout.splitlines() if line.strip() and "__pycache__" not in line]


def protocol_contents():
    from matchup_dna import heldout
    from matchup_dna.audit_tennisdata import sackmann_overlap
    from matchup_dna.crosswalk import load_player_names
    from matchup_dna.experiment import PROTOCOL_PATH as PHASE3_PROTOCOL, sha256
    from matchup_dna.phase4_features import DATASET_DIR, FILES
    from matchup_dna.phase4_model import GROUP_COLUMNS, PHASE3_GROUPS
    from matchup_dna.tennisdata import SEAL_START, provider_files
    from matchup_dna.tennisismylife import SEAL_DATE, tml_files

    selection, round_choice = load_selection(), json.loads(ROUND_AWARE_PATH.read_text(encoding="utf-8"))
    gbm = json.loads(GBM_PATH.read_text(encoding="utf-8")) if GBM_PATH.exists() else None
    serve_return = next(gap for group, passed, gap in selection["trail"] if group == "serve_return")
    profile_payload = json.loads(PROFILE_SETTINGS.read_text(encoding="utf-8"))
    inputs = ([DATASET_DIR / FILES[name] for name in ("train", "validation", "retrospective")]
              + [PROFILE_SETTINGS, SELECTION_PATH, ROUND_AWARE_PATH] + ([GBM_PATH] if gbm else [])
              + [PHASE4_DIR / "crosswalk.csv", PHASE4_DIR / "tml_crosswalk.csv", PHASE3_PROTOCOL]
              + sackmann_inputs() + provider_files() + tml_files())
    used_groups = set(selection["groups"]) | set(round_choice["kept_groups"]) | set(round_choice["r0_groups"]) | {"elo"}
    return {
        "phase": 4,
        "frozen": datetime.date.today().isoformat(),
        "git_commit": git_commit(),
        "code_commit": head_commit(),
        "code_paths": list(CODE_PATHS),
        "deviation_policy": "The frozen procedure is run as written. An unexpected or unfavorable retrospective or held-out "
                            "result is reported, never acted on: no feature, setting, or sample changes after either is "
                            "seen. Only a genuine implementation defect may interrupt the procedure; its correction is "
                            "documented, committed as a new version, and reported next to the original run.",
        "feature_columns": {group: list(GROUP_COLUMNS[group]) for group in sorted(used_groups)},
        "feature_definitions": "matchup_dna/phase4_model.py (columns), matchup_dna/profiles.py (profile estimates), "
                               "matchup_dna/round_aware.py (round-aware values), at git_commit",
        "profile_means": profile_payload["means"],
        "primary_claim": "P4-refit against P3-refit on identical held-out matches, tournament-start track",
        "tournament_start": {
            "baseline": {"name": "P3-refit", "groups": list(PHASE3_GROUPS), "l2": {"ATP": 1000.0, "WTA": 100.0}},
            "model": {"name": "P4-refit", "groups": list(selection["groups"]), "l2": selection["l2"],
                      "representations": selection["representations"]},
            "continuity": "P3-original: the Phase 3 final model as fitted on 2010-2023",
            "secondary": ({"name": "LightGBM", "groups": list(selection["groups"]), "settings": gbm["settings"]}
                          if gbm and gbm["passed_against_logistic"] else None),
        },
        "round_aware": {"sample": "eligible matches after the edition's first round (Data Audit A6-A7)",
                        "reference": "P4-refit predictions", "R0": {"groups": round_choice["r0_groups"], "l2": round_choice["r0_l2"]},
                        "kept": {"groups": round_choice["kept_groups"], "l2": round_choice["l2"]}},
        "profiles": json.loads(PROFILE_SETTINGS.read_text(encoding="utf-8"))["settings"],
        "training": "development models fitted on 2010-2020 per tour; L2 chosen on the inner split (fit 2010-2017, score "
                    "2018-2020); selection by the Phase 3 keep rule on 2021-2023 (experiments/phase4_log.md)",
        "refit": "every model refitted per tour on all rated matches from 2010 to the week of 25 May 2026, L2 held at the "
                 "values above; P3-original fitted on 2010-2023; profile settings and means held fixed",
        "retrospective": {"command": "python -m matchup_dna.phase4_experiment retrospective",
                          "rows": "2024 to the week of 25 May 2026 (results/phase4/retrospective.csv), seen once in Phase 3",
                          "models": "fitted on 2010-2023 with the L2 values above", "runs": "once; reported as a "
                          "robustness check, not a fresh test; nothing is changed after it"},
        "held_out": {"command": "python -m matchup_dna.phase4_experiment holdout --confirm",
                     "seal": {"TennisData.app": f"match day on or after {SEAL_START}", "TML": f"tourney_date on or after {SEAL_DATE}"},
                     "editions_starting": [HELD_OUT[0], "before " + str(HELD_OUT[1])],
                     "complete_before_snapshot": "2026-11-05; ongoing-file editions excluded",
                     "population": "main-tour main draws; no qualifying, wheelchair, Challenger or WTA 125",
                     "excluded_tennisdata_tournaments": heldout.excluded_tournaments(sackmann_overlap(), load_player_names()),
                     "sources": "TML rows; TennisData.app rows only where no TML row matches (names in the -3 to +16 day "
                                "window, then validated ids), not the same pair and round within 3 days of a TML row, and "
                                "not a pair and round Sackmann already holds within 14 days",
                     "players": "validated crosswalks (results/phase4/crosswalk.csv, tml_crosswalk.csv), else a unique "
                                "full-name (TML) or surname-and-initial (TennisData.app) match to a Sackmann player with "
                                "tour-level matches since 2015, else a provider-only id",
                     "edition_date": "TennisData.app first main-draw day when the edition is in TennisData.app, else TML's "
                                     "earliest date",
                     "best_of": "from the tournament (ATP Grand Slam main draw = 5), never from the sets played",
                     "rated": "completed best-of-3 and best-of-5 matches", "ranks": "provider ranks (TML, else TennisData.app)",
                     "statistics": "TML counts; TennisData.app-only matches carry no statistics",
                     "output": "results/phase4/final/ (refuses to run if it exists)"},
        "metrics": "log loss (primary), Brier, accuracy, paired log-loss gaps with standard errors clustered by tournament "
                   "date and by month, reliability and calibration line; ATP, WTA, and combined; by month, surface, and "
                   "round",
        "minimum_detectable_gain": {
            "tournament-start": minimum_detectable(serve_return[1], 16039, EXPECTED_HELD_OUT["tournament-start"]),
            "round-aware": minimum_detectable(round_choice["gaps"]["R0 vs reference"][1], round_choice["validation_rows"],
                                              EXPECTED_HELD_OUT["round-aware"]),
        },
        "reporting_rule": "a gain is called an improvement only if its 95% interval excludes zero",
        "inputs": {str(path.relative_to(EXPERIMENTS_DIR.parent)): sha256(path) for path in inputs},
    }


def freeze(dry_run):
    if PROTOCOL_PATH.exists() and not dry_run:
        raise SystemExit(f"{PROTOCOL_PATH} already exists. It is never overwritten.")
    changes = uncommitted_code()
    if changes and not dry_run:
        raise SystemExit("Commit the code before freezing, so the protocol records an exact commit:\n" + "\n".join(changes))
    contents = protocol_contents()
    print(json.dumps(contents, indent=2))
    if dry_run:
        print("\nDry run: nothing written.")
        return
    PROTOCOL_PATH.write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    print(f"\nWritten to {PROTOCOL_PATH}. Commit it before running retrospective or holdout.")


def require_committed_protocol():
    import subprocess
    from matchup_dna.experiment import ROOT
    if not PROTOCOL_PATH.exists():
        raise SystemExit("No frozen Phase 4 protocol. Run `freeze` and commit the file first.")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(PROTOCOL_PATH)], cwd=ROOT, capture_output=True)
    changed = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(PROTOCOL_PATH)], cwd=ROOT)
    if tracked.returncode != 0 or changed.returncode != 0:
        raise SystemExit(f"{PROTOCOL_PATH} must be committed, unchanged, before outcomes are opened.")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    check_frozen_state(protocol)
    return protocol


AMENDMENT_PATH = EXPERIMENTS_DIR / "phase4_protocol_amendment_1.json"
AMENDMENT_REASON = (
    "Implementation defect found when `holdout --confirm` first ran on 2026-11-05: merge.tml_match refused every TML "
    "row whose `sealed` flag was set, including held-out rows correctly unlocked by the frozen protocol, so the "
    "command stopped while assembling its first held-out match. No held-out output was printed, scored, or written. "
    "The rehearsal had not exercised this path because its January-May 2026 rows were never sealed.")
AMENDMENT_FIX = (
    "merge.tml_match now refuses only rows without a winner column (the sealed view); a regression test checks that an "
    "unlocked held-out row converts and a sealed row is still refused. phase4_experiment gains this amendment record "
    "and its check. No model, feature, parameter, dataset, input file, or protocol value changed.")


def git_ok(*arguments):
    import subprocess
    from matchup_dna.experiment import ROOT
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True).returncode == 0


def changed_code_files(old, new, paths):
    import subprocess
    from matchup_dna.experiment import ROOT
    found = subprocess.run(["git", "diff", "--name-only", old, new, "--", *paths], cwd=ROOT, capture_output=True, text=True)
    return sorted(found.stdout.split())


def amend():
    """Writes amendment 1: the corrected code commit for the frozen procedure, after a documented defect. Refuses to
    overwrite, and requires the original protocol and the corrected code to be committed and the inputs unchanged."""
    from matchup_dna.experiment import sha256
    if AMENDMENT_PATH.exists():
        raise SystemExit(f"{AMENDMENT_PATH} already exists. It is never overwritten.")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if not git_ok("ls-files", "--error-unmatch", str(PROTOCOL_PATH)) or not git_ok("diff", "--quiet", "HEAD", "--", str(PROTOCOL_PATH)):
        raise SystemExit("The original protocol must be committed and unchanged.")
    check_inputs(protocol)
    if uncommitted_code():
        raise SystemExit("Commit the corrected code first, so the amendment records an exact commit:\n" + "\n".join(uncommitted_code()))
    head = head_commit()
    contents = {
        "amendment": 1, "amends": str(PROTOCOL_PATH.relative_to(EXPERIMENTS_DIR.parent)),
        "amends_sha256": sha256(PROTOCOL_PATH), "created": datetime.date.today().isoformat(),
        "reason": AMENDMENT_REASON, "fix": AMENDMENT_FIX,
        "original_code_commit": protocol["code_commit"], "code_commit": head,
        "changed_files": changed_code_files(protocol["code_commit"], head, protocol["code_paths"]),
        "results_seen_before_the_fix": "the retrospective check (2024-May 2026) only; no held-out result",
        "inputs_unchanged": True,
    }
    AMENDMENT_PATH.write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(contents, indent=2))
    print(f"\nWritten to {AMENDMENT_PATH}. Commit it before running holdout.")


def check_inputs(protocol):
    from matchup_dna.experiment import ROOT, sha256
    changed = [path for path, digest in protocol["inputs"].items()
               if not (ROOT / path).exists() or sha256(ROOT / path) != digest]
    if changed:
        raise SystemExit("Inputs differ from the frozen protocol, so the frozen procedure cannot run:\n" + "\n".join(changed))


def frozen_code_commit(protocol):
    """The commit the frozen procedure must run on: the protocol's, or a committed amendment's. An amendment counts
    only if it is committed unchanged, names this protocol by its hash, and lists exactly the code files that differ
    between the two commits."""
    from matchup_dna.experiment import sha256
    if not AMENDMENT_PATH.exists():
        return protocol["code_commit"], None
    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    if not git_ok("ls-files", "--error-unmatch", str(AMENDMENT_PATH)) or not git_ok("diff", "--quiet", "HEAD", "--", str(AMENDMENT_PATH)):
        raise SystemExit(f"{AMENDMENT_PATH} must be committed, unchanged.")
    if amendment["amends_sha256"] != sha256(PROTOCOL_PATH) or amendment["original_code_commit"] != protocol["code_commit"]:
        raise SystemExit("The amendment does not belong to this protocol.")
    if changed_code_files(protocol["code_commit"], amendment["code_commit"], protocol["code_paths"]) != amendment["changed_files"]:
        raise SystemExit("The code changed by the amendment is not exactly the files it lists.")
    return amendment["code_commit"], amendment


def check_frozen_state(protocol):
    """Stops unless every hashed input is unchanged and the code equals the frozen commit (or a committed
    amendment's corrected commit)."""
    check_inputs(protocol)
    commit, _ = frozen_code_commit(protocol)
    if uncommitted_code():
        raise SystemExit("The code has uncommitted changes; the frozen procedure runs only on the frozen code.")
    if changed_code_files(commit, "HEAD", protocol["code_paths"]):
        raise SystemExit(f"The code under {protocol['code_paths']} has changed since the frozen commit {commit}.")


def score_period(out, title, rows, models, extra=None):
    from matchup_dna.model import labels
    y = labels(rows)
    from matchup_dna.experiment import print_breakdown
    predictions = {name: predict(models, rows, name) for name in ("P3-refit", "P4-refit")}
    predictions.update(extra or {})
    report_models(out, title, rows, y, predictions, "P3-refit")
    print_breakdown(out, f"{title} by month", rows, y, predictions, lambda row: row["tourney_date"] // 100)
    print_breakdown(out, f"{title} by round", rows, y, predictions, lambda row: row["round"])
    ra_rows = [r for r in rows if r["ra_later_round"]]
    if ra_rows:
        ra_y = labels(ra_rows)
        ra_predictions = {"Reference (P4-refit)": predict(models, ra_rows, "P4-refit"),
                          "R0": predict(models, ra_rows, "R0"), "RA-kept": predict(models, ra_rows, "RA-kept")}
        report_models(out, f"{title}, round-aware track", ra_rows, ra_y, ra_predictions, "R0")
        print_breakdown(out, f"{title}, round-aware track by round", ra_rows, ra_y, ra_predictions,
                        lambda row: row["round"])
    return predictions


def retrospective():
    protocol = require_committed_protocol()
    if RETROSPECTIVE_DIR.exists():
        raise SystemExit(f"{RETROSPECTIVE_DIR} exists: the retrospective check has run.")
    from matchup_dna.phase4_features import load_phase4
    out = Output()
    rows = load_phase4("retrospective", unseal_with=PROTOCOL_PATH)
    fit_rows = load_phase4("train") + load_phase4("validation")
    selection = {"groups": tuple(protocol["tournament_start"]["model"]["groups"]), "l2": protocol["tournament_start"]["model"]["l2"]}
    reps = protocol["tournament_start"]["model"]["representations"]
    models = fit_final_models(fit_rows, selection, reps, {
        "r0_groups": protocol["round_aware"]["R0"]["groups"], "r0_l2": protocol["round_aware"]["R0"]["l2"],
        "kept_groups": protocol["round_aware"]["kept"]["groups"], "l2": protocol["round_aware"]["kept"]["l2"]})
    out("Retrospective robustness check on 2024 to the week of 25 May 2026. These matches were scored once in")
    out("Phase 3, so this is not a fresh test. Models fitted on 2010-2023 under the frozen Phase 4 protocol.")
    score_period(out, "Retrospective 2024-May 2026", rows, models)
    RETROSPECTIVE_DIR.mkdir(parents=True)
    save("retrospective", out, [PROTOCOL_PATH], ["Retrospective check run; see results/phase4/experiments/retrospective.txt"])
    (RETROSPECTIVE_DIR / "done.txt").write_text("run\n", encoding="utf-8")


def holdout(confirm):
    if not confirm:
        raise SystemExit("The held-out evaluation runs once. Add --confirm after the protocol is frozen and committed.")
    if FINAL_DIR.exists():
        raise SystemExit(f"{FINAL_DIR} exists, so the held-out evaluation has already run.")
    protocol = require_committed_protocol()
    import csv as csv_module
    from matchup_dna.features import LABEL
    from matchup_dna.model import LogisticModel
    from matchup_dna.phase4_model import PHASE3_GROUPS

    out = Output()
    commit, amendment = frozen_code_commit(protocol)
    if amendment:
        out(f"Running under amendment {amendment['amendment']} (code {commit}): {amendment['reason']}")
        out(f"Fix: {amendment['fix']}")
        out()
    # The frozen procedure as it ran; erratum 1's corrected rebuild is phase4_correction.
    rows, keys, report, _ = provider_period(*HELD_OUT, unseal_with=PROTOCOL_PATH, version=1)
    fit_rows = [r for r in rows if 20100101 <= r["tourney_date"] < HELD_OUT[0]]
    held = [r for r in rows if r["tourney_date"] >= HELD_OUT[0]]
    out(f"Held-out evaluation, editions starting {HELD_OUT[0]} to {HELD_OUT[1]}, scored once. {len(held):,} rated "
        f"matches; models refitted on {len(fit_rows):,} matches from 2010 to the week of 25 May 2026.")
    for key, value in report.items():
        out(f"   {key}: {value}")
    selection = {"groups": tuple(protocol["tournament_start"]["model"]["groups"]), "l2": protocol["tournament_start"]["model"]["l2"]}
    reps = protocol["tournament_start"]["model"]["representations"]
    models = fit_final_models(fit_rows, selection, reps, {
        "r0_groups": protocol["round_aware"]["R0"]["groups"], "r0_l2": protocol["round_aware"]["R0"]["l2"],
        "kept_groups": protocol["round_aware"]["kept"]["groups"], "l2": protocol["round_aware"]["kept"]["l2"]})
    import numpy as np
    original = np.empty(len(held))
    for tour, l2 in protocol["tournament_start"]["baseline"]["l2"].items():
        index = [i for i, r in enumerate(held) if r["tour"] == tour]
        model = LogisticModel(PHASE3_GROUPS, l2).fit([r for r in fit_rows if r["tour"] == tour and r["tourney_date"] < 20240101])
        original[index] = model.predict([held[i] for i in index])
    predictions = score_period(out, "Held-out June-October 2026", held, models, {"P3-original": original})
    out(f"\nPre-registered minimum detectable gains: {json.dumps(protocol['minimum_detectable_gain'])}")
    out("Reporting rule: a gain is called an improvement only if its 95% interval excludes zero.")
    FINAL_DIR.mkdir(parents=True)
    with open(FINAL_DIR / "heldout_predictions.csv", "w", encoding="utf-8", newline="") as file:
        writer = csv_module.writer(file)
        writer.writerow(["match_id", "tourney_date", "tour", "a_id", "b_id", LABEL] + list(predictions))
        for i, row in enumerate(held):
            writer.writerow([row["match_id"], row["tourney_date"], row["tour"], row["a_id"], row["b_id"], row[LABEL]]
                            + [f"{predictions[name][i]:.6f}" for name in predictions])
    save("holdout", out, [PROTOCOL_PATH], ["Held-out evaluation run; see results/phase4/experiments/holdout.txt"],
         extra={"protocol": protocol, "amendment": amendment})


# ---------------------------------------------------------------- tour-average diagnostic

def experiment_mean_check():
    """Do the fixed 2010-2020 tour averages leak information? Repeats the profile tuning, the profile features, and
    the validation comparison with strictly point-in-time averages (each year's from the five years before it).
    A diagnostic: nothing it finds changes the frozen choice; a material difference would be reported as a defect."""
    import numpy as np
    from matchup_dna.experiment import describe_keep, keep_rule, per_tour
    from matchup_dna.features import match_id
    from matchup_dna.phase4_features import PROFILE_FIELDS
    from matchup_dna.phase4_model import PHASE3_GROUPS
    from matchup_dna.profiles import HALF_LIVES, PRIOR_MATCHES, ProfileEngine, prior_year_averages, replay, to_ordinal
    from matchup_dna.selection import logistic
    from matchup_dna.workload import load_matches_with_workload

    out = Output()
    settings = json.loads(PROFILE_SETTINGS.read_text(encoding="utf-8"))
    fixed = {tour: {stat: tuple(v) for stat, v in stats.items()} for tour, stats in settings["means"].items()}
    matches = load_matches_with_workload()
    timely = prior_year_averages(matches)
    out("Tour-average diagnostic. Fixed averages (2010-2020, used by the model) against strictly point-in-time")
    out("averages (each year from the five calendar years before it).\n")
    out("1. The averages, by year: service points won share mu (fixed / point-in-time), and points per match d")
    for tour in ("ATP", "WTA"):
        parts = []
        for year in range(2010, 2024):
            mu, d = timely(tour, to_ordinal(year * 10000 + 701))["serve"]
            parts.append(f"{year} {mu:.4f}")
        out(f"   {tour}: fixed {fixed[tour]['serve'][0]:.4f} (d {fixed[tour]['serve'][1]:.1f}); point-in-time "
            + ", ".join(parts))

    out("\n2. Profile tuning repeated with point-in-time averages (history before each match, scored 2018-2020)")
    before_scoring = [m for m in matches if m["tourney_date"] < PROFILE_SCORE[1]]
    tuning = {}
    for tour in ("ATP", "WTA"):
        subset = [m for m in before_scoring if m["tour"] == tour]
        options = []
        for half_life in HALF_LIVES:
            for prior in PRIOR_MATCHES:
                _, scores = replay(subset, ProfileEngine(timely, half_life, prior), score_window=PROFILE_SCORE)
                options += [(scores[(tour, kind)], half_life, prior, kind) for kind in ("raw", "adjusted")]
                baseline = scores[(tour, "tour average")]
        best = min(options)
        frozen = settings["settings"][tour]
        tuning[tour] = best
        same = (best[1], best[2], best[3]) == (frozen["half_life"], frozen["prior_matches"], frozen["representation"])
        out(f"   {tour}: chosen half-life {best[1]}, prior {best[2]}, {best[3]} (loss {best[0]:.5f}; tour average "
            f"{baseline:.5f}); frozen {frozen['half_life']}, {frozen['prior_matches']}, {frozen['representation']} "
            f"-> {'same choice' if same else 'DIFFERENT CHOICE'}")

    out("\n3. Profile features with point-in-time averages and the frozen settings, against the dataset's")
    timely_profiles = {}
    for tour, chosen in settings["settings"].items():
        engine = ProfileEngine(timely, chosen["half_life"], chosen["prior_matches"])
        found, _ = replay([m for m in matches if m["tour"] == tour and m["tourney_date"] < 20240101], engine,
                          keep_from=20100101)
        timely_profiles.update(found)
    by_id = {match_id(m): m for m in matches}
    train, validation, y, inputs = development()

    def substituted(rows):
        changed = []
        for row in rows:
            match = by_id[row["match_id"]]
            sides = ("winner", "loser") if row["a_id"] == match["winner_id"] else ("loser", "winner")
            copy = dict(row)
            for letter, side in zip(("a", "b"), sides):
                values = timely_profiles[(match["key"], side)]
                for field in PROFILE_FIELDS:
                    copy[f"{letter}_{field}"] = values[field]
            changed.append(copy)
        return changed

    timely_train, timely_validation = substituted(train), substituted(validation)
    for label, original, other in (("training", train, timely_train), ("validation", validation, timely_validation)):
        for field in ("serve_adjusted", "return_adjusted"):
            a = np.array([r[f"a_{field}"] for r in original])
            b = np.array([r[f"a_{field}"] for r in other])
            gap_a = np.log(a / (1 - a)) - np.log(np.array([r[f"b_{field}"] for r in original]) /
                                                  (1 - np.array([r[f"b_{field}"] for r in original])))
            gap_b = np.log(b / (1 - b)) - np.log(np.array([r[f"b_{field}"] for r in other]) /
                                                  (1 - np.array([r[f"b_{field}"] for r in other])))
            out(f"   {label} {field}: mean |difference| {np.mean(np.abs(a - b)):.5f}, largest {np.max(np.abs(a - b)):.5f};"
                f" A-minus-B logit gap correlation {np.corrcoef(gap_a, gap_b)[0, 1]:.5f}")

    out("\n4. Validation comparison repeated on the point-in-time features (frozen groups and L2)")
    selection, reps = load_selection(), representations()
    base = per_tour(train, validation, logistic(PHASE3_GROUPS, selection["baseline_l2"], reps))
    for label, fit_rows, rows in (("fixed averages (as selected)", train, validation),
                                  ("point-in-time averages", timely_train, timely_validation)):
        p = per_tour(fit_rows, rows, logistic(selection["groups"], selection["l2"], reps))
        describe_keep(out, f"{label}: chosen vs Phase 3 groups", keep_rule(validation, y, p, base))
    save("mean-check", out, inputs + [PROFILE_SETTINGS], [
        f"{tour}: point-in-time tuning chose {t[1]}, {t[2]}, {t[3]}" for tour, t in tuning.items()])


# ---------------------------------------------------------------- verification

TRUNCATION_CUT = 20220704
PHASE4_START_COMMIT = "9b24fd6"


def experiment_verify():
    """Reproducibility and leakage checks before the freeze. Reads no sealed outcome."""
    import csv as csv_module
    import io
    import subprocess
    from matchup_dna import tennisdata as td
    from matchup_dna import tennisismylife as tml
    from matchup_dna.experiment import PROTOCOL_PATH as PHASE3_PROTOCOL, ROOT, sha256
    from matchup_dna.features import DATASET_DIR as PHASE3_DIR, FILES as PHASE3_FILES, build_rows
    from matchup_dna.phase4_features import DATASET_DIR, FILES, augment, backfilled_matches

    out = Output()
    problems = []

    def check(ok, text):
        out(f"   [{'ok' if ok else 'FAIL'}] {text}")
        if not ok:
            problems.append(text)

    out("1. Phases 1-3 unchanged")
    frozen = json.loads(PHASE3_PROTOCOL.read_text(encoding="utf-8"))
    for key, digest in frozen["inputs"].items():
        check(sha256(ROOT / key.replace("\\", "/")) == digest, f"{key} matches the Phase 3 frozen hash")
    final_manifest = json.loads((PHASE3_DIR / "final" / "final_manifest.json").read_text(encoding="utf-8"))
    differing = [k for k, v in final_manifest["inputs"].items() if sha256(ROOT / k.replace("\\", "/")) != v]
    check(not differing, f"all {len(final_manifest['inputs'])} inputs of the Phase 3 final run (protocol, reserved "
                         f"features, every Sackmann file) re-hash to their recorded values")
    phase3_paths = ["matchup_dna/" + n for n in ("load.py", "elo.py", "features.py", "model.py", "experiment.py",
                    "evaluate.py", "periods.py", "calibrate.py", "stats.py", "validate.py")] + [
                    "experiments/frozen_protocol.json", "experiments/log.md", "Phase 2 - Elo Report.md"]
    # 9b24fd6 is the last commit before Phase 4 began. (The Phase 3 final run appended its entry to the Phase 3 log after
    # c373447, and that entry was committed in 850b1b9, so c373447 is not the right reference.)
    diff = subprocess.run(["git", "diff", "--name-only", PHASE4_START_COMMIT, "HEAD", "--", *phase3_paths], cwd=ROOT,
                          capture_output=True, text=True).stdout.split()
    local = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *phase3_paths], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    check(not diff and not local, f"Phase 1-3 code, frozen protocol, Phase 3 log, and Phase 2 report unchanged since "
                                  f"Phase 4 began ({PHASE4_START_COMMIT}), committed and in the working tree")

    out("\n2. The Phase 4 dataset reproduces Phase 3 and repeats no match")
    for name, phase3_name in (("train", "train"), ("validation", "validation"), ("retrospective", "reserved")):
        with open(DATASET_DIR / FILES[name], encoding="utf-8", newline="") as file:
            mine = list(csv_module.DictReader(file))
        with open(PHASE3_DIR / PHASE3_FILES[phase3_name], encoding="utf-8", newline="") as file:
            theirs = list(csv_module.DictReader(file))
        check(len(mine) == len(theirs), f"{FILES[name]}: {len(mine):,} rows, as Phase 3 ({len(theirs):,})")
        check(len({r["match_id"] for r in mine}) == len(mine), f"{FILES[name]}: every match_id appears once")
        same = all(all(a[field] == b[field] for field in b) for a, b in zip(mine, theirs))
        check(same, f"{FILES[name]}: every Phase 3 column equals Phase 3's file, cell for cell")

    out(f"\n3. No later information: rebuild with history cut at {TRUNCATION_CUT} and compare every earlier row")
    matches, _ = backfilled_matches()
    cut = [m for m in matches if m["tourney_date"] < TRUNCATION_CUT]
    rebuilt = augment(build_rows(cut), cut, PROFILE_SETTINGS)
    full = {}
    for name in ("train", "validation"):
        with open(DATASET_DIR / FILES[name], encoding="utf-8", newline="") as file:
            for row in csv_module.DictReader(file):
                if int(row["tourney_date"]) < TRUNCATION_CUT:
                    full[row["match_id"]] = row
    fields = list(next(iter(full.values())))
    buffer = io.StringIO(newline="")
    writer = csv_module.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rebuilt)
    buffer.seek(0)
    rebuilt_rows = {row["match_id"]: row for row in csv_module.DictReader(buffer)}
    mismatched = Counter()
    for match_id, row in full.items():
        other = rebuilt_rows.get(match_id)
        if other is None:
            mismatched["row missing from the truncated build"] += 1
            continue
        for field in fields:
            if row[field] != other[field]:
                mismatched[field] += 1
    check(len(rebuilt_rows) == len(full) and not mismatched,
          f"{len(full):,} rows before the cut: all {len(fields)} columns identical whether or not later matches exist"
          + (f" (differences: {dict(mismatched.most_common(8))})" if mismatched else ""))

    out("\n4. Sealed outcomes stay sealed")
    tml_rows, td_rows = tml.load_tml(), td.load_provider()
    sealed_tml = [r for r in tml_rows if r["sealed"]]
    sealed_td = [r for r in td_rows if r["sealed"]]
    check(not any(c in r for r in sealed_tml for c in tml.OUTCOME_COLUMNS),
          f"{len(sealed_tml):,} sealed TML rows carry none of the {len(tml.OUTCOME_COLUMNS)} outcome columns")
    check(not any(c in r for r in sealed_td for c in td.SEALED_COLUMNS),
          f"{len(sealed_td):,} sealed TennisData.app rows carry none of the {len(td.SEALED_COLUMNS)} sealed columns")
    check(not FINAL_DIR.exists() and not RETROSPECTIVE_DIR.exists() and not PROTOCOL_PATH.exists(),
          "no frozen Phase 4 protocol, no retrospective run, no held-out run")
    callers = subprocess.run(["git", "grep", "-n", "unseal_with=PROTOCOL_PATH", "--", "matchup_dna"], cwd=ROOT,
                             capture_output=True, text=True).stdout.splitlines()
    local_callers = [line for line in callers if "def " not in line and "git grep" not in line and '"grep"' not in line]
    out(f"   unsealing calls in committed code: {len(local_callers)} (retrospective loader and held-out command only)")

    out("\n5. Git")
    tracked = subprocess.run(["git", "ls-files", "data", "results"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    check(not tracked, "no file under data/ or results/ is tracked")
    for folder in ("data/external/tennisdata_app", "data/external/tennisismylife", "results/phase4"):
        ignored = subprocess.run(["git", "check-ignore", "-q", folder + "/x.csv"], cwd=ROOT).returncode == 0
        check(ignored, f"{folder}/ is ignored")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    out(f"   staged files: {staged or 'none'}")
    out(f"\n{'ALL CHECKS PASSED' if not problems else f'{len(problems)} CHECKS FAILED'}")
    save("verify", out, [PHASE3_PROTOCOL], [f"verification: {'passed' if not problems else problems}"])
    if problems:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Phase 4 experiments")
    parser.add_argument("command", choices=["profiles", "dataset", "tournament", "gbm", "round-aware", "rehearse",
                                            "mean-check", "verify", "freeze", "amend", "retrospective", "holdout"])
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.command == "freeze":
        return freeze(args.dry_run)
    if args.command == "holdout":
        return holdout(args.confirm)
    if args.command == "amend":
        return amend()
    {"profiles": experiment_profiles, "dataset": experiment_dataset, "tournament": experiment_tournament,
     "gbm": experiment_gbm, "round-aware": experiment_round_aware, "rehearse": experiment_rehearse,
     "mean-check": experiment_mean_check, "verify": experiment_verify, "retrospective": retrospective}[args.command]()


if __name__ == "__main__":
    sys.exit(main())

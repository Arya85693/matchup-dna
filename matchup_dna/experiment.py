"""Phase 3 experiments. Development commands read only the train and validation files.

    python -m matchup_dna.experiment calibration   Experiment A
    python -m matchup_dna.experiment elo-lr        Experiment B
    python -m matchup_dna.experiment features      Experiment C
    python -m matchup_dna.experiment gbm           Experiment D
    python -m matchup_dna.experiment same-k        K and surface-blend diagnostic
    python -m matchup_dna.experiment freeze        writes experiments/frozen_protocol.json
    python -m matchup_dna.experiment final --protocol experiments/frozen_protocol.json --confirm

`final` is the only code that rebuilds reserved-period outcomes. It runs once: it stops if its output folder exists.
"""
import argparse
import csv
import datetime
import hashlib
import json
import platform
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from matchup_dna import calibrate
from matchup_dna.elo import RESULTS_DIR, run_elo, win_probability
from matchup_dna.evaluate import calibration, clustered_standard_error
from matchup_dna.features import DATASET_DIR, FILES, LABEL, build_rows, load_split, parse_row
from matchup_dna.load import DATA_DIR, TOURS, load_matches, match_files
from matchup_dna.model import (
    GROUP_ORDER,
    LogisticModel,
    choose_l2,
    derived_columns,
    feature_names,
    fit_preprocessing,
    labels,
    mean_log_loss,
)
from matchup_dna.periods import DEVELOPMENT_END, DEVELOPMENT_START, period

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS_DIR = ROOT / "experiments"
LOG_PATH = EXPERIMENTS_DIR / "log.md"
PROTOCOL_PATH = EXPERIMENTS_DIR / "frozen_protocol.json"
OUTPUT_DIR = DATASET_DIR / "experiments"
FINAL_DIR = DATASET_DIR / "final"

# The keep rule, fixed before Experiment C: a change is kept only if combined validation log loss falls by
# more than KEEP_COMBINED_SE clustered standard errors, neither tour gets worse by more than KEEP_TOUR_SE of
# its own standard error, and at least KEEP_YEARS validation years improve.
KEEP_COMBINED_SE = 2.0
KEEP_TOUR_SE = 1.0
KEEP_YEARS = 2

GBM_LEAVES = (7, 15, 31)
GBM_LEARNING_RATE = 0.05
GBM_MIN_CHILD = 400
GBM_MAX_TREES = 3000
GBM_EARLY_STOP = 100
GBM_INNER_START = 20180101


class Output:
    """Prints lines and keeps them, so each command's output can be saved next to its manifest."""

    def __init__(self):
        self.lines = []

    def __call__(self, text=""):
        print(text)
        self.lines.append(text)


# ---------------------------------------------------------------- probabilities and scores

def winner_probability(p, y):
    return np.where(y == 1, p, 1 - p)


def match_log_loss(p, y):
    return -np.log(np.clip(winner_probability(p, y), 1e-12, 1))


def scores(p, y):
    w = winner_probability(p, y)
    accuracy = np.where(w > 0.5, 1.0, np.where(w == 0.5, 0.5, 0.0)).mean()
    return {"matches": len(y), "log_loss": float(match_log_loss(p, y).mean()),
            "brier": float(((1 - w) ** 2).mean()), "accuracy": float(accuracy)}


def paired_gap(p_new, p_old, y, weeks):
    """Mean per-match log loss of new minus old, and its standard error clustered by tourney_date."""
    differences = match_log_loss(p_new, y) - match_log_loss(p_old, y)
    return float(differences.mean()), clustered_standard_error(list(differences), list(weeks))


def masks(rows):
    tours = np.array([row["tour"] for row in rows])
    return {"ATP": tours == "ATP", "WTA": tours == "WTA", "Both": np.ones(len(rows), dtype=bool)}


def keep_rule(rows, y, p_new, p_old):
    weeks = np.array([row["tourney_date"] for row in rows])
    years = weeks // 10000
    result = {}
    for name, mask in masks(rows).items():
        result[name] = paired_gap(p_new[mask], p_old[mask], y[mask], weeks[mask])
    improved = sum(
        match_log_loss(p_new[years == year], y[years == year]).mean()
        < match_log_loss(p_old[years == year], y[years == year]).mean()
        for year in np.unique(years)
    )
    combined, combined_se = result["Both"]
    passed = (
        combined < -KEEP_COMBINED_SE * combined_se
        and all(result[tour][0] < KEEP_TOUR_SE * result[tour][1] for tour in TOURS)
        and improved >= KEEP_YEARS
    )
    return {"gaps": result, "years_improved": int(improved), "years": len(np.unique(years)), "passed": bool(passed)}


def describe_keep(out, label, outcome):
    gaps = outcome["gaps"]
    parts = "  ".join(f"{name} {gap:+.4f} (se {se:.4f})" for name, (gap, se) in gaps.items())
    verdict = "KEEP" if outcome["passed"] else "reject"
    out(f"   {label:<44} {parts}  years better {outcome['years_improved']}/{outcome['years']}  -> {verdict}")


def print_scores_table(out, title, rows, y, models):
    out(f"\n{title}")
    out(f"   {'model':<40} {'tour':<5} {'matches':>8}  logloss  brier   accuracy")
    for name, p in models.items():
        for tour, mask in masks(rows).items():
            s = scores(p[mask], y[mask])
            out(f"   {name:<40} {tour:<5} {s['matches']:>8,}  {s['log_loss']:.4f}  {s['brier']:.4f}  {s['accuracy']:.2%}")


def print_gaps(out, title, rows, y, models, baseline):
    weeks = np.array([row["tourney_date"] for row in rows])
    out(f"\n{title} (log loss per match minus {baseline}; negative is better; se clustered by tourney_date)")
    for name, p in models.items():
        if name == baseline:
            continue
        parts = []
        for tour, mask in masks(rows).items():
            gap, se = paired_gap(p[mask], models[baseline][mask], y[mask], weeks[mask])
            parts.append(f"{tour} {gap:+.4f} (se {se:.4f})")
        out(f"   {name:<40} " + "  ".join(parts))


def print_breakdown(out, title, rows, y, models, key):
    out(f"\n{title} (log loss)")
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[(row["tour"], key(row))].append(index)
    names = list(models)
    out(f"   {'tour':<5} {'group':<10} {'matches':>8}  " + "  ".join(f"{name[:22]:>22}" for name in names))
    for group in sorted(groups, key=lambda item: (item[0], str(item[1]))):
        index = np.array(groups[group])
        values = "  ".join(f"{scores(models[name][index], y[index])['log_loss']:>22.4f}" for name in names)
        out(f"   {group[0]:<5} {str(group[1]):<10} {len(index):>8,}  {values}")


def print_reliability(out, title, rows, y, models):
    for tour, mask in masks(rows).items():
        if tour == "Both":
            continue
        out(f"\nReliability, {title}, {tour}: favorite's probability bucket, matches, predicted, observed")
        for name, p in models.items():
            parts = [
                f"{low:.1f}-{high:.1f}: {count:,} {predicted:.3f}/{observed:.3f}"
                for low, high, count, predicted, observed in calibration(list(winner_probability(p[mask], y[mask])))
            ]
            out(f"   {name:<34} " + "  ".join(parts))


# ---------------------------------------------------------------- fitting by tour

def tour_rows(rows, tour):
    return [row for row in rows if row["tour"] == tour]


def per_tour(fit_rows, target_rows, fit_predict):
    """Runs fit_predict(fitting rows, target rows) -> probabilities separately for each tour."""
    p = np.empty(len(target_rows))
    for tour in TOURS:
        index = [i for i, row in enumerate(target_rows) if row["tour"] == tour]
        p[index] = fit_predict(tour_rows(fit_rows, tour), [target_rows[i] for i in index])
    return p


def raw(field):
    def fit_predict(fit_rows, target_rows):
        return np.array([row[field] for row in target_rows], dtype=float)
    return fit_predict


def temperature(field, start=None):
    def fit_predict(fit_rows, target_rows):
        fitting = [row for row in fit_rows if start is None or row["tourney_date"] >= start]
        b = calibrate.fit_temperature(np.array([row[field] for row in fitting]), labels(fitting))
        return calibrate.apply_temperature(np.array([row[field] for row in target_rows]), b)
    return fit_predict


def logistic(groups, l2):
    """l2 is one value or {tour: value}."""
    def fit_predict(fit_rows, target_rows):
        value = l2[fit_rows[0]["tour"]] if isinstance(l2, dict) else l2
        return LogisticModel(groups, value).fit(fit_rows).predict(target_rows)
    return fit_predict


def chosen_l2(rows, groups):
    return {tour: choose_l2(tour_rows(rows, tour), groups)[0] for tour in TOURS}


def baselines(fit_rows, target_rows):
    return {
        "Elo": per_tour(fit_rows, target_rows, raw("elo_probability")),
        "Surface Elo": per_tour(fit_rows, target_rows, raw("surface_elo_probability")),
        "Elo, temperature": per_tour(fit_rows, target_rows, temperature("elo_probability")),
        "Surface Elo, temperature": per_tour(fit_rows, target_rows, temperature("surface_elo_probability")),
    }


# ---------------------------------------------------------------- gradient boosting

def gbm_matrix(rows, groups, preprocessing):
    """Antisymmetric features of the chosen groups, then symmetric context. Returns (X, number antisymmetric)."""
    derived = derived_columns(rows, preprocessing)
    names = [name for name in feature_names(groups) if name != "surface_logit_x_experience"]
    antisymmetric = [derived[name] for name in names]
    a_matches = np.array([row["a_elo_matches"] for row in rows], dtype=float)
    b_matches = np.array([row["b_elo_matches"] for row in rows], dtype=float)
    symmetric = [
        np.log1p(np.minimum(a_matches, b_matches)),
        np.array([row["best_of"] == 5 for row in rows], dtype=float),
        np.array([row["surface"] == "Clay" for row in rows], dtype=float),
        np.array([row["surface"] == "Grass" for row in rows], dtype=float),
    ]
    return np.column_stack(antisymmetric + symmetric), len(antisymmetric)


def flipped(X, antisymmetric):
    flip = X.copy()
    flip[:, :antisymmetric] *= -1
    return flip


def gbm_fit(rows, groups, leaves, trees=None, early_rows=None):
    """Trained on both orderings of every match. With early_rows, stops early on them and returns the tree count."""
    import lightgbm

    preprocessing = fit_preprocessing(rows)
    X, k = gbm_matrix(rows, groups, preprocessing)
    y = labels(rows)
    params = {
        "objective": "binary", "learning_rate": GBM_LEARNING_RATE, "num_leaves": leaves,
        "min_child_samples": GBM_MIN_CHILD, "verbose": -1, "seed": 0, "deterministic": True,
        "force_row_wise": True, "num_threads": 1,
    }
    train_set = lightgbm.Dataset(np.vstack([X, flipped(X, k)]), np.concatenate([y, 1 - y]))
    if early_rows is not None:
        Xe, _ = gbm_matrix(early_rows, groups, preprocessing)
        ye = labels(early_rows)
        valid = lightgbm.Dataset(np.vstack([Xe, flipped(Xe, k)]), np.concatenate([ye, 1 - ye]), reference=train_set)
        booster = lightgbm.train(params, train_set, GBM_MAX_TREES, valid_sets=[valid],
                                 callbacks=[lightgbm.early_stopping(GBM_EARLY_STOP, verbose=False)])
        return booster, preprocessing, k
    return lightgbm.train(params, train_set, trees), preprocessing, k


def gbm_predict(model, rows, groups):
    booster, preprocessing, k = model
    X, _ = gbm_matrix(rows, groups, preprocessing)
    return 0.5 * (booster.predict(X) + 1 - booster.predict(flipped(X, k)))


def gbm_tune(rows, groups):
    """Leaves and tree count chosen inside the fitting rows: fit before GBM_INNER_START, stop early on the rest."""
    early = [row for row in rows if row["tourney_date"] < GBM_INNER_START]
    late = [row for row in rows if row["tourney_date"] >= GBM_INNER_START]
    results = {}
    for leaves in GBM_LEAVES:
        model = gbm_fit(early, groups, leaves, early_rows=late)
        results[leaves] = (mean_log_loss(gbm_predict(model, late, groups), labels(late)), model[0].best_iteration)
    leaves = min(results, key=lambda key: results[key][0])
    return {"leaves": leaves, "trees": results[leaves][1]}, results


def gbm(groups, settings):
    def fit_predict(fit_rows, target_rows):
        chosen = settings[fit_rows[0]["tour"]]
        return gbm_predict(gbm_fit(fit_rows, groups, chosen["leaves"], chosen["trees"]), target_rows, groups)
    return fit_predict


# ---------------------------------------------------------------- record keeping

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit():
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return commit + ("+uncommitted" if dirty else "")
    except OSError:
        return "unknown"


def manifest(name, inputs, extra=None):
    import lightgbm
    import sklearn

    return {
        "command": name,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "packages": {"numpy": np.__version__, "lightgbm": lightgbm.__version__, "scikit-learn": sklearn.__version__},
        "inputs": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        **(extra or {}),
    }


def save(name, out, inputs, summary, extra=None, directory=OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    record = manifest(name, inputs, extra)
    (directory / f"{name}_manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    EXPERIMENTS_DIR.mkdir(exist_ok=True)
    new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", encoding="utf-8") as log:
        if new:
            log.write("# Phase 3 experiment log\n\nOne entry per run, appended by `python -m matchup_dna.experiment`.\n")
        log.write(f"\n## {record['created']} · {name}\n\ncommit `{record['git_commit']}`\n\n")
        for line in summary:
            log.write(f"- {line}\n")


def development():
    train, validation = load_split("train"), load_split("validation")
    inputs = [DATASET_DIR / FILES["train"], DATASET_DIR / FILES["validation"]]
    return train, validation, labels(validation), inputs


# ---------------------------------------------------------------- experiments

def experiment_calibration():
    out = Output()
    train, validation, y, inputs = development()
    out("Experiment A: recalibrating Elo. Fitted on 2010-2020, scored on 2021-2023, separately per tour.")

    out("\nFitted parameters on 2010-2020")
    for tour in TOURS:
        rows = tour_rows(train, tour)
        target = labels(rows)
        for field in ("elo_probability", "surface_elo_probability"):
            p = np.array([row[field] for row in rows])
            b = calibrate.fit_temperature(p, target)
            a, platt_b = calibrate.fit_platt(p, target)
            recent = [row for row in rows if row["tourney_date"] >= 20160101]
            b_recent = calibrate.fit_temperature(np.array([row[field] for row in recent]), labels(recent))
            out(f"   {tour} {field:<24} temperature b = {b:.4f}   2016-2020 only b = {b_recent:.4f}"
                f"   Platt a = {a:+.4f}, b = {platt_b:.4f}")

    models = baselines(train, validation)
    pooled = {}
    for field, label in (("elo_probability", "Elo"), ("surface_elo_probability", "Surface Elo")):
        b = calibrate.fit_temperature(np.array([row[field] for row in train]), labels(train))
        pooled[label] = b
        models[f"{label}, temperature both tours"] = calibrate.apply_temperature(
            np.array([row[field] for row in validation]), b)
        models[f"{label}, temperature 2016-2020"] = per_tour(train, validation, temperature(field, 20160101))
    out(f"   Both tours pooled: Elo b = {pooled['Elo']:.4f}, Surface Elo b = {pooled['Surface Elo']:.4f}")

    print_scores_table(out, "Validation 2021-2023", validation, y, models)
    print_gaps(out, "Against raw Elo", validation, y, models, "Elo")
    print_gaps(out, "Against raw surface Elo", validation, y, models, "Surface Elo")
    print_reliability(out, "validation", validation, y,
                      {k: models[k] for k in ("Surface Elo", "Surface Elo, temperature", "Elo", "Elo, temperature")})
    gap = keep_rule(validation, y, models["Surface Elo, temperature"], models["Surface Elo"])
    save("calibration", out, inputs, [
        "Temperature scaling per tour, fitted on 2010-2020; benchmark is 'Surface Elo, temperature'.",
        f"Surface Elo, temperature vs raw surface Elo on validation: " + ", ".join(
            f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in gap["gaps"].items()),
    ])


def experiment_elo_lr():
    out = Output()
    train, validation, y, inputs = development()
    out("Experiment B: logistic regression on the Elo and surface Elo log-odds, no intercept, per tour.")
    l2 = chosen_l2(train, ())
    out(f"\nL2 chosen inside 2010-2020 (fit 2010-2017, score 2018-2020): {l2}")
    out("Coefficients (1.0 on a log-odds feature reproduces that Elo model exactly)")
    for tour in TOURS:
        model = LogisticModel((), l2[tour]).fit(tour_rows(train, tour))
        coefficients = model.unscaled_coefficients()
        total = sum(coefficients.values())
        out(f"   {tour}: " + ", ".join(f"{k} {v:.4f}" for k, v in coefficients.items())
            + f"   sum {total:.4f}, surface share {coefficients['surface_elo_logit'] / total:.3f}")

    models = baselines(train, validation)
    models["Logistic, Elo features"] = per_tour(train, validation, logistic((), l2))
    print_scores_table(out, "Validation 2021-2023", validation, y, models)
    print_gaps(out, "Against surface Elo, temperature", validation, y, models, "Surface Elo, temperature")
    print_gaps(out, "Against raw surface Elo", validation, y, models, "Surface Elo")
    out("\nKeep rule, logistic on Elo features vs surface Elo, temperature")
    outcome = keep_rule(validation, y, models["Logistic, Elo features"], models["Surface Elo, temperature"])
    describe_keep(out, "Logistic, Elo features", outcome)
    save("elo-lr", out, inputs, [f"L2 {l2}", f"vs calibrated surface Elo: passed={outcome['passed']}, "
                                 + ", ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in outcome["gaps"].items())])


def select_groups(train, validation, y, out):
    """Forward selection over GROUP_ORDER from the Elo-only logistic model, using the keep rule on validation."""
    groups = ()
    l2 = chosen_l2(train, groups)
    current = per_tour(train, validation, logistic(groups, l2))
    out("\nForward selection, each group added to the current model")
    trail = []
    for group in GROUP_ORDER:
        candidate = groups + (group,)
        candidate_l2 = chosen_l2(train, candidate)
        p = per_tour(train, validation, logistic(candidate, candidate_l2))
        outcome = keep_rule(validation, y, p, current)
        describe_keep(out, f"+ {group} (L2 {candidate_l2})", outcome)
        trail.append((group, outcome))
        if outcome["passed"]:
            groups, l2, current = candidate, candidate_l2, p
    return groups, l2, current, trail


def experiment_features():
    out = Output()
    train, validation, y, inputs = development()
    out("Experiment C: feature groups added to the Elo logistic model in a fixed order, kept by the keep rule.")
    out(f"Keep rule: combined gap < -{KEEP_COMBINED_SE} se, each tour gap < +{KEEP_TOUR_SE} se, "
        f">= {KEEP_YEARS} of 3 validation years better.")

    out("\nMissing values in the inputs (rows where either player's value is missing)")
    for name, rows in (("train", train), ("validation", validation)):
        for tour in TOURS:
            sub = tour_rows(rows, tour)
            rank = np.mean([r["a_rank"] is None or r["b_rank"] is None for r in sub])
            days = np.mean([r["a_days_since"] is None or r["b_days_since"] is None for r in sub])
            form = np.mean([min(r["a_form_matches"], r["b_form_matches"]) == 0 for r in sub])
            out(f"   {name:<10} {tour}: rank {rank:.2%}, no previous match {days:.2%}, no form history {form:.2%}")

    groups, l2, selected, trail = select_groups(train, validation, y, out)
    out(f"\nSelected groups: {list(groups) or 'none beyond Elo'}; L2 {l2}")

    base_l2 = chosen_l2(train, ())
    base = per_tour(train, validation, logistic((), base_l2))
    out("\nAblation: each group alone on the Elo logistic model")
    for group in GROUP_ORDER:
        group_l2 = chosen_l2(train, (group,))
        p = per_tour(train, validation, logistic((group,), group_l2))
        describe_keep(out, f"Elo + {group}", keep_rule(validation, y, p, base))
    if groups:
        out("\nAblation: each selected group removed from the selected model")
        for group in groups:
            fewer = tuple(g for g in groups if g != group)
            p = per_tour(train, validation, logistic(fewer, chosen_l2(train, fewer)))
            describe_keep(out, f"selected - {group} (vs selected)", keep_rule(validation, y, p, selected))

    out("\nCoefficients of the selected model, fitted on 2010-2020 (feature units, not scaled)")
    for tour in TOURS:
        model = LogisticModel(groups, l2[tour]).fit(tour_rows(train, tour))
        out(f"   {tour}: " + ", ".join(f"{k} {v:+.5f}" for k, v in model.unscaled_coefficients().items()))

    models = baselines(train, validation)
    models["Logistic, Elo features"] = base
    models["Logistic, selected"] = selected
    print_scores_table(out, "Validation 2021-2023", validation, y, models)
    print_gaps(out, "Against surface Elo, temperature", validation, y, models, "Surface Elo, temperature")
    print_breakdown(out, "Validation by surface", validation, y, models, lambda row: row["surface"] or "missing")
    print_breakdown(out, "Validation by year", validation, y, models, lambda row: row["tourney_date"] // 10000)
    print_reliability(out, "validation", validation, y,
                      {k: models[k] for k in ("Surface Elo, temperature", "Logistic, selected")})

    keep = np.array([row["overlap_flag"] == 0 for row in validation])
    out(f"\nRobustness: validation without the {int((~keep).sum()):,} matches where a player's previous event may overlap")
    subset = [row for row, k in zip(validation, keep) if k]
    print_gaps(out, "Without overlap-flagged matches", subset, y[keep],
               {name: p[keep] for name, p in models.items()}, "Surface Elo, temperature")

    save("features", out, inputs, [f"Selected groups {list(groups)}, L2 {l2}"] + [
        f"+{group}: passed={outcome['passed']}, combined {outcome['gaps']['Both'][0]:+.4f} "
        f"(se {outcome['gaps']['Both'][1]:.4f})" for group, outcome in trail
    ], extra={"selected_groups": list(groups), "l2": l2})


def experiment_gbm():
    out = Output()
    train, validation, y, inputs = development()
    groups, l2, selected, _ = select_groups(train, validation, y, Output())
    out(f"Experiment D: LightGBM on the selected groups {list(groups)} plus symmetric context, trained on both")
    out("orderings of each match. Leaves and tree count chosen inside 2010-2020 (fit 2010-2017, stop on 2018-2020).")
    settings = {}
    for tour in TOURS:
        settings[tour], results = gbm_tune(tour_rows(train, tour), groups)
        out(f"   {tour}: " + ", ".join(f"{leaves} leaves: inner log loss {ll:.4f} at {trees} trees"
                                       for leaves, (ll, trees) in results.items()) + f" -> {settings[tour]}")
    models = baselines(train, validation)
    models["Logistic, selected"] = selected
    models["LightGBM"] = per_tour(train, validation, gbm(groups, settings))
    print_scores_table(out, "Validation 2021-2023", validation, y, models)
    print_gaps(out, "Against logistic, selected", validation, y, models, "Logistic, selected")
    outcome = keep_rule(validation, y, models["LightGBM"], models["Logistic, selected"])
    out("\nKeep rule, LightGBM vs logistic, selected")
    describe_keep(out, "LightGBM", outcome)
    save("gbm", out, inputs, [f"settings {settings}", f"vs selected logistic: passed={outcome['passed']}, combined "
                              f"{outcome['gaps']['Both'][0]:+.4f} (se {outcome['gaps']['Both'][1]:.4f})"],
         extra={"settings": settings, "passed": outcome["passed"]})


def experiment_same_k():
    out = Output()
    out("Same-K diagnostic: overall-only and half-surface Elo at K = 32 and K = 48, log loss, 2010-2023 only.")
    out("Diagnostic only. The official baselines stay Elo K = 32 and surface Elo K = 48.")
    matches = load_matches()
    predictions = {}
    for k in (32, 48):
        found, _ = run_elo(matches, ("fixed", k), before=DEVELOPMENT_END)
        predictions[k] = [p for p in found if p["match"]["tourney_date"] >= DEVELOPMENT_START]
    for name in ("train", "validation"):
        for tour in TOURS:
            chosen = {k: [p for p in v if period(p["match"]["tourney_date"]) == name and p["match"]["tour"] == tour]
                      for k, v in predictions.items()}
            weeks = [p["match"]["tourney_date"] for p in chosen[32]]
            values = {}
            for k in (32, 48):
                values[f"Elo K{k}"] = np.array([win_probability(p) for p in chosen[k]])
                values[f"Surface K{k}"] = np.array([win_probability(p, 0.5) for p in chosen[k]])
            ones = np.ones(len(weeks))
            line = "  ".join(f"{label} {match_log_loss(v, ones).mean():.4f}" for label, v in values.items())
            gains = "; ".join(
                "surface gain at K{0} {1:+.4f} (se {2:.4f})".format(
                    k, *paired_gap(values[f"Surface K{k}"], values[f"Elo K{k}"], ones, weeks))
                for k in (32, 48))
            out(f"   {name:<10} {tour}: {line}\n      {gains}")
    save("same-k", out, [], ["Same-K diagnostic on 2010-2023; see results/phase3/experiments/same-k.txt"])


def protocol_contents():
    train, validation, y, inputs = development()
    groups, l2, selected, _ = select_groups(train, validation, y, Output())
    gbm_settings, gbm_passed = None, False
    gbm_record = OUTPUT_DIR / "gbm_manifest.json"
    if gbm_record.exists():
        record = json.loads(gbm_record.read_text(encoding="utf-8"))
        gbm_settings, gbm_passed = record["settings"], record["passed"]
    return {
        "frozen": datetime.date.today().isoformat(),
        "git_commit": git_commit(),
        "model": "logistic",
        "secondary": "lightgbm" if gbm_passed else None,
        "groups": list(groups),
        "logistic_l2": l2,
        "lightgbm_settings": gbm_settings if gbm_passed else None,
        "fit_years": "2010-2023",
        "calibrated_benchmarks": "temperature scaling per tour, fitted on 2010-2023",
        "comparisons": ["Elo", "Surface Elo", "Elo, temperature", "Surface Elo, temperature"],
        "secondary_comparisons": ["Surface Elo, temperature", "Selected model"] if gbm_passed else [],
        "primary_metric": "log loss, per tour and combined, paired against each comparison, se clustered by tourney_date",
        "robustness": "repeat the paired comparisons without overlap-flagged matches",
        "inputs": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
    }


def freeze():
    if PROTOCOL_PATH.exists():
        raise SystemExit(f"{PROTOCOL_PATH} already exists. Delete it deliberately to re-freeze.")
    contents = protocol_contents()
    EXPERIMENTS_DIR.mkdir(exist_ok=True)
    PROTOCOL_PATH.write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(contents, indent=2))
    print(f"\nWritten to {PROTOCOL_PATH}. Commit it before running final.")


# ---------------------------------------------------------------- final evaluation

def reserved_rows_with_labels():
    """Rebuilds the reserved rows from the raw files, labels included, and checks them against the saved features."""
    rebuilt = [row for row in build_rows(load_matches()) if row["period"] == "reserved"]
    with open(DATASET_DIR / FILES["reserved"], encoding="utf-8", newline="") as file:
        saved = [parse_row(row) for row in csv.DictReader(file)]
    if [row["match_id"] for row in rebuilt] != [row["match_id"] for row in saved]:
        raise SystemExit("Rebuilt reserved rows do not match reserved_features.csv")
    for row, saved_row in zip(rebuilt, saved):
        for field in ("a_id", "b_id", "elo_diff", "surface_elo_diff", "a_rank", "b_rank"):
            if (row[field] is None) != (saved_row[field] is None) or (
                    row[field] is not None and abs(row[field] - saved_row[field]) > 1e-6):
                raise SystemExit(f"Rebuilt reserved row {row['match_id']} differs in {field}")
    return rebuilt


def final(protocol_path, confirm):
    if not confirm:
        raise SystemExit("Final evaluation runs once. Add --confirm after the protocol is frozen and committed.")
    if FINAL_DIR.exists():
        raise SystemExit(f"{FINAL_DIR} exists, so the final evaluation has already run.")
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    out = Output()
    fit_rows = load_split("train") + load_split("validation")
    reserved = reserved_rows_with_labels()
    y = labels(reserved)
    out(f"Final evaluation on {len(reserved):,} reserved matches, models fitted on {len(fit_rows):,} 2010-2023 matches.")
    out(f"Protocol {protocol_path} sha256 {sha256(Path(protocol_path))}")

    groups = tuple(protocol["groups"])
    models = baselines(fit_rows, reserved)
    if protocol["model"] == "lightgbm":
        models["Logistic, selected"] = per_tour(fit_rows, reserved, logistic(groups, protocol["logistic_l2"]))
        models["Selected model"] = per_tour(fit_rows, reserved, gbm(groups, protocol["lightgbm_settings"]))
    else:
        models["Selected model"] = per_tour(fit_rows, reserved, logistic(groups, protocol["logistic_l2"]))
    if protocol.get("secondary") == "lightgbm":
        models["LightGBM, secondary"] = per_tour(fit_rows, reserved, gbm(groups, protocol["lightgbm_settings"]))
    out(f"Selected model: {protocol['model']} with groups {list(groups)}; secondary: {protocol.get('secondary')}")

    print_scores_table(out, "Reserved 2024 to May 2026", reserved, y, models)
    for baseline in protocol["comparisons"]:
        print_gaps(out, f"Against {baseline}", reserved, y, {k: models[k] for k in (baseline, "Selected model")}, baseline)
    if "LightGBM, secondary" in models:
        for baseline in protocol["secondary_comparisons"]:
            print_gaps(out, f"Secondary against {baseline}", reserved, y,
                       {k: models[k] for k in (baseline, "LightGBM, secondary")}, baseline)
    print_breakdown(out, "Reserved by surface", reserved, y, models, lambda row: row["surface"] or "missing")
    print_breakdown(out, "Reserved by year", reserved, y, models, lambda row: row["tourney_date"] // 10000)
    print_reliability(out, "reserved", reserved, y,
                      {k: models[k] for k in ("Surface Elo", "Surface Elo, temperature", "Selected model",
                                              "LightGBM, secondary") if k in models})
    keep = np.array([row["overlap_flag"] == 0 for row in reserved])
    subset = [row for row, k in zip(reserved, keep) if k]
    print_gaps(out, f"Robustness, without {int((~keep).sum()):,} overlap-flagged matches", subset, y[keep],
               {name: p[keep] for name, p in models.items()}, "Surface Elo, temperature")

    FINAL_DIR.mkdir(parents=True)
    with open(FINAL_DIR / "reserved_predictions.csv", "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["match_id", "tourney_date", "tour", "a_id", "b_id", LABEL] + list(models))
        for index, row in enumerate(reserved):
            writer.writerow([row["match_id"], row["tourney_date"], row["tour"], row["a_id"], row["b_id"], row[LABEL]]
                            + [f"{models[name][index]:.6f}" for name in models])
    raw_files = [path for tour in TOURS for path in match_files(tour, DATA_DIR)]
    save("final", out, [Path(protocol_path).resolve(), DATASET_DIR / FILES["reserved"]] + raw_files,
         ["Final evaluation run. See results/phase3/final/final.txt"], extra={"protocol": protocol},
         directory=FINAL_DIR)


def main():
    parser = argparse.ArgumentParser(description="Phase 3 experiments")
    parser.add_argument("command", choices=["calibration", "elo-lr", "features", "gbm", "same-k", "freeze", "final"])
    parser.add_argument("--protocol", default=str(PROTOCOL_PATH))
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    commands = {
        "calibration": experiment_calibration, "elo-lr": experiment_elo_lr, "features": experiment_features,
        "gbm": experiment_gbm, "same-k": experiment_same_k, "freeze": freeze,
    }
    if args.command == "final":
        final(args.protocol, args.confirm)
    else:
        commands[args.command]()


if __name__ == "__main__":
    sys.exit(main())

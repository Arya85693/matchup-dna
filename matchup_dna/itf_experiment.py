"""ITF extension, stage I3: development, validation, the freeze and the one-time held-out test.

    python -m matchup_dna.itf_experiment rows       feature rows before 2026 for every Elo variant and both pools
                                                     (results/itf/rows/, sealed: no 2026 row is built)
    python -m matchup_dna.itf_experiment develop    the Elo variant and each tour's L2, chosen on development only
    python -m matchup_dna.itf_experiment validate   B0, B1, B2, M1 and M2 fitted on development and scored on
                                                     validation (July-December 2025); M2 is chosen over M1 only if
                                                     the 95% interval of its improvement excludes zero. Runs once.
    python -m matchup_dna.itf_experiment freeze     experiments/itf_frozen_protocol.json: the choices above, the
                                                     code fingerprint and the split record's SHA-256. Needs the
                                                     code committed. Run only after the user approves (gate 2).
    python -m matchup_dna.itf_experiment holdout --confirm
                                                     after the protocol is committed (gate 3): refit the chosen model
                                                     on development + validation, score January-June 2026 once

The held-out rows can be built only once the protocol is committed (itf_splits.unsealed), and `holdout` refuses to
run twice. See "docs/ITF - Data Audit and Plan.md", section 4, for the rules declared before any of this ran.
"""
import argparse
import csv
import datetime
import gc
import hashlib
import json
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np

from matchup_dna import itf_data, itf_features, itf_model, itf_ratings, itf_splits
from matchup_dna.elo import RESULTS_DIR

ROOT = Path(__file__).resolve().parent.parent
OUT = RESULTS_DIR / "itf"
ROWS_DIR = OUT / "rows"
DEVELOPMENT = OUT / "development.json"
VALIDATION = OUT / "validation.json"
HOLDOUT = OUT / "holdout.json"
PROTOCOL = itf_splits.PROTOCOL_PATH
TOURS = ("ATP", "WTA")
FROZEN_MODEL = ROOT / "models" / "phase4_tournament_start.json"
CODE_FILES = ("matchup_dna/itf_splits.py", "matchup_dna/itf_data.py", "matchup_dna/itf_ratings.py",
              "matchup_dna/itf_features.py", "matchup_dna/itf_model.py", "matchup_dna/itf_experiment.py",
              "matchup_dna/elo.py", "matchup_dna/features.py", "matchup_dna/load.py", "matchup_dna/model.py",
              "matchup_dna/periods.py", "matchup_dna/phase4_model.py", "matchup_dna/phase4_features.py",
              "matchup_dna/profiles.py", "matchup_dna/serve_stats.py", "matchup_dna/workload.py",
              "models/phase4_tournament_start.json")
UNTRACKED_INPUTS = ("results/phase4/profile_settings.json",)      # B2's profile averages (gitignored results/)


def now_text():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def text_sha256(path):
    """SHA-256 of a text file with line endings normalized, so Windows and Linux checkouts agree."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def code_hashes():
    """{file: SHA-256}, None for a file that is missing (the untracked input exists only where Phase 4 ran), so a
    protocol frozen with it present refuses a checkout without it."""
    return {name: text_sha256(ROOT / name) if (ROOT / name).exists() else None for name in CODE_FILES + UNTRACKED_INPUTS}


def rows_path(tour, variant, pool, sealed=True):
    return ROWS_DIR / f"{tour}_{variant}_{pool}{'' if sealed else '_with_2026'}.pkl"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_rows(tour, variant, pool, sealed=True):
    with open(rows_path(tour, variant, pool, sealed), "rb") as f:
        return pickle.load(f)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- rows

def build(allow_held_out, variants, b2=True, log=print):
    """Rows for each tour, variant and pool. Profiles do not depend on the Elo variant, so each pool's are built once."""
    sealed = not allow_held_out
    summary = {}
    for tour in TOURS:
        matches = itf_data.load(allow_held_out=allow_held_out, tours=(tour,))
        log(f"{tour}: {len(matches):,} matches loaded")
        means = itf_features.itf_serve_means(matches)
        profiles = itf_features.pool_profiles(matches, "every_level", means)
        for variant in variants:
            rows = itf_features.build_rows(matches, variant, profiles=profiles)
            save(rows_path(tour, variant, "every_level", sealed), rows)
            log(f"{tour} {variant}: {len(rows):,} rows")
            summary[f"{tour} {variant} every_level"] = len(rows)
            del rows
        del profiles
        gc.collect()
        if b2:
            profiles = itf_features.pool_profiles(matches, "main_only")
            rows = itf_features.build_rows(matches, "phase2", "main_only", profiles=profiles)
            save(rows_path(tour, "phase2", "main_only", sealed), rows)
            log(f"{tour} main_only: {len(rows):,} rows")
            summary[f"{tour} phase2 main_only"] = len(rows)
            del rows, profiles
        summary[f"{tour} itf_serve_means"] = {stat: list(v) for stat, v in means[tour].items()}
        del matches
        gc.collect()
    return summary


def split_rows(rows, *names):
    return [row for row in rows if row["split"] in names]


# ---------------------------------------------------------------- develop

def develop():
    if not rows_path("ATP", "phase2", "every_level").exists():
        raise SystemExit("run `rows` first")
    variants = {}
    for variant in itf_ratings.VARIANTS:
        per_tour, losses = {}, []
        for tour in TOURS:
            rows = split_rows(load_rows(tour, variant, "every_level"), "development")
            p, y = itf_model.elo_probability(rows), itf_model.labels(rows)
            per_tour[tour] = itf_model.metrics(p, y)
            losses.append(itf_model.row_losses(p, y))
        pooled = np.concatenate(losses)
        variants[variant] = {"pooled_log_loss": float(pooled.mean()), "matches": int(len(pooled)), "tours": per_tour}
    chosen = min(variants, key=lambda v: variants[v]["pooled_log_loss"])
    l2 = {}
    for tour in TOURS:
        rows = split_rows(load_rows(tour, chosen, "every_level"), "development")
        best, scores = itf_model.choose_l2(rows, "M1")
        b0, b0_scores = itf_model.choose_l2(rows, "B0")
        l2[tour] = {"M1": best, "M2": best, "B0": b0, "M1_inner_scores": scores, "B0_inner_scores": b0_scores}
    result = {"created_at": now_text(), "elo_variants": variants, "chosen_variant": chosen, "l2": l2,
              "rule": "variant: lowest pooled development log loss of the ordinary Elo probability; L2: fit before "
                      f"{itf_model.INNER_START}, score development rows from then on; M2 uses M1's L2"}
    write_json(DEVELOPMENT, result)
    return result


# ---------------------------------------------------------------- validate

def frozen_model():
    from matchup_dna.forecasting.frozen_models import FrozenModel
    return FrozenModel(FROZEN_MODEL.read_text(encoding="utf-8"))


def score(fit_rows, test_rows, b2_rows, l2, b2_model):
    """{model: predictions on test_rows} for B0, B1, B2, M1, M2."""
    predictions = {"B1": itf_model.elo_probability(test_rows)}
    for name in itf_model.FITTED:
        predictions[name] = itf_model.ITFLogistic(name, l2[name]).fit(fit_rows).predict(test_rows)
    by_id = {row["match_id"]: row for row in b2_rows}
    aligned = [by_id[row["match_id"]] for row in test_rows]
    if any(a["a_id"] != t["a_id"] or a["a_won"] != t["a_won"] for a, t in zip(aligned, test_rows)):
        raise SystemExit("B2 rows do not line up with the scored rows")
    predictions["B2"] = b2_model.predict(aligned)
    return predictions


def compare(predictions, rows, against, models):
    y = itf_model.labels(rows)
    clusters = [(row["tour"], row["tourney_id"]) for row in rows]
    base = itf_model.row_losses(predictions[against], y)
    return {f"{name} - {against}": itf_model.paired_bootstrap(itf_model.row_losses(predictions[name], y), base, clusters)
            for name in models}


def evaluate(variant, l2, fit_splits, test_split, sealed=True):
    """Fits on `fit_splits`, scores `test_split`; returns (summary, prediction rows)."""
    b2_model = frozen_model()
    all_rows, all_predictions, tours = [], {name: [] for name in ("B0", "B1", "B2", "M1", "M2")}, {}
    for tour in TOURS:
        rows = load_rows(tour, variant, "every_level", sealed)
        fit_rows, test_rows = split_rows(rows, *fit_splits), split_rows(rows, test_split)
        b2_rows = split_rows(load_rows(tour, "phase2", "main_only", sealed), test_split)
        predictions = score(fit_rows, test_rows, b2_rows, l2[tour], b2_model)
        y = itf_model.labels(test_rows)
        tours[tour] = {name: itf_model.metrics(p, y) for name, p in predictions.items()}
        tours[tour]["fit_rows"] = len(fit_rows)
        tours[tour]["serve_stats_share"] = float(np.mean([bool(r["a_serve_attempts"]) and bool(r["b_serve_attempts"])
                                                          for r in test_rows]))
        all_rows += test_rows
        for name, p in predictions.items():
            all_predictions[name].append(p)
    predictions = {name: np.concatenate(parts) for name, parts in all_predictions.items()}
    y = itf_model.labels(all_rows)
    summary = {"pooled": {name: itf_model.metrics(p, y) for name, p in predictions.items()}, "tours": tours,
               "comparisons": {**compare(predictions, all_rows, "M1", ("M2",)),
                               **compare(predictions, all_rows, "B0", ("M1", "M2")),
                               **compare(predictions, all_rows, "B1", ("M1", "M2")),
                               **compare(predictions, all_rows, "B2", ("M1", "M2"))},
               "by_tier": by_tier(predictions, all_rows)}
    table = [{"match_id": r["match_id"], "tourney_date": r["tourney_date"], "tour": r["tour"], "tier": r["tier"],
              "a_name": r["a_name"], "b_name": r["b_name"], "a_won": r["a_won"],
              **{f"p_{name}": float(predictions[name][i]) for name in predictions}} for i, r in enumerate(all_rows)]
    return summary, table


def by_tier(predictions, rows):
    found = {}
    for tour in TOURS:
        for tier in sorted({r["tier"] for r in rows if r["tour"] == tour}):
            index = [i for i, r in enumerate(rows) if r["tour"] == tour and r["tier"] == tier]
            y = itf_model.labels([rows[i] for i in index])
            found[f"{tour} tier {tier}"] = {name: {"matches": len(index),
                                                   "log_loss": itf_model.mean_log_loss(p[index], y)}
                                            for name, p in predictions.items()}
    return found


def write_predictions(path, table):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)


def validate():
    if VALIDATION.exists():
        raise SystemExit(f"{VALIDATION} exists: validation runs once")
    dev = json.loads(DEVELOPMENT.read_text(encoding="utf-8"))
    l2 = {tour: {name: dev["l2"][tour][name] for name in itf_model.FITTED} for tour in TOURS}
    summary, table = evaluate(dev["chosen_variant"], l2, ("development",), "validation")
    improvement = summary["comparisons"]["M2 - M1"]
    chosen = "M2" if improvement["ci95"][1] < 0 else "M1"
    result = {"created_at": now_text(), "variant": dev["chosen_variant"], "l2": l2, "chosen_model": chosen,
              "rule": "M2 if the 95% interval of (M2 - M1) validation log loss lies below zero, else M1", **summary}
    write_json(VALIDATION, result)
    write_predictions(OUT / "validation_predictions.csv", table)
    return result


# ---------------------------------------------------------------- freeze and holdout

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def freeze():
    if PROTOCOL.exists():
        raise SystemExit(f"{PROTOCOL.name} exists")
    dirty = [name for name in CODE_FILES + ("experiments/itf_splits.json",)
             if git("ls-files", "--error-unmatch", name).returncode or git("diff", "--quiet", "HEAD", "--", name).returncode]
    if dirty:
        raise SystemExit("commit these first, so the protocol names committed code: " + ", ".join(dirty))
    if itf_splits.check():
        raise SystemExit("the split record's check fails")
    dev = json.loads(DEVELOPMENT.read_text(encoding="utf-8"))
    val = json.loads(VALIDATION.read_text(encoding="utf-8"))
    protocol = {
        "name": "ITF extension frozen protocol",
        "frozen_at": now_text(),
        "code_commit": git("rev-parse", "HEAD").stdout.strip(),
        "code_sha256": code_hashes(),
        "splits_sha256": itf_splits.sha256(itf_splits.SPLITS_PATH),
        "development_sha256": itf_splits.sha256(DEVELOPMENT),
        "validation_sha256": itf_splits.sha256(VALIDATION),
        "elo_variant": dev["chosen_variant"],
        "chosen_model": val["chosen_model"],
        "l2": val["l2"],
        "final_fit": "each fitted model refitted per tour on development + validation rows (all ITF rows before 2026)",
        "held_out": "every rated ITF main-draw match from 2026-01-01 to the end of the data, scored once",
        "primary": f"log loss of {val['chosen_model']} against B0 (rank only), B1 (Elo only) and B2 (production "
                   "main-tour model), paired bootstrap by edition; reported pooled, by tour and by tier",
    }
    PROTOCOL.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    return protocol


def holdout(confirm):
    if not confirm:
        raise SystemExit("the held-out test runs once: pass --confirm")
    if HOLDOUT.exists():
        raise SystemExit(f"{HOLDOUT} exists: the held-out test has run")
    if not itf_splits.unsealed():
        raise SystemExit("the seal is on: commit experiments/itf_frozen_protocol.json first")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = [name for name, digest in code_hashes().items() if protocol["code_sha256"].get(name) != digest]
    if changed:
        raise SystemExit("code differs from the frozen protocol: " + ", ".join(changed))
    if itf_splits.check():
        raise SystemExit("the split record's check fails")
    build(True, (protocol["elo_variant"],))
    summary, table = evaluate(protocol["elo_variant"], protocol["l2"], ("development", "validation"), "held_out",
                              sealed=False)
    result = {"created_at": now_text(), "protocol_sha256": itf_splits.sha256(PROTOCOL),
              "chosen_model": protocol["chosen_model"], **summary}
    write_json(HOLDOUT, result)
    write_predictions(OUT / "holdout_predictions.csv", table)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("rows", "develop", "validate", "freeze", "holdout"))
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "rows":
        summary = build(False, tuple(itf_ratings.VARIANTS))
        write_json(OUT / "rows_summary.json", {"created_at": now_text(), **summary})
    elif args.command == "develop":
        result = develop()
        for variant, v in result["elo_variants"].items():
            print(f"{variant:11s} development Elo log loss {v['pooled_log_loss']:.4f} ({v['matches']:,} matches)")
        print(f"chosen: {result['chosen_variant']}; L2 {{tour: M1}} =", {t: v['M1'] for t, v in result['l2'].items()})
    elif args.command == "validate":
        result = validate()
        for name, m in result["pooled"].items():
            print(f"{name}: log loss {m['log_loss']:.4f}  Brier {m['brier']:.4f}  accuracy {m['accuracy']:.3f}")
        c = result["comparisons"]["M2 - M1"]
        print(f"M2 - M1 {c['mean']:+.4f} (se {c['se']:.4f}, 95% {c['ci95'][0]:+.4f} to {c['ci95'][1]:+.4f}) -> "
              f"chosen {result['chosen_model']}")
    elif args.command == "freeze":
        protocol = freeze()
        print(f"froze {PROTOCOL.name}: {protocol['elo_variant']} Elo, {protocol['chosen_model']}; commit it next")
    else:
        result = holdout(args.confirm)
        for name, m in result["pooled"].items():
            print(f"{name}: log loss {m['log_loss']:.4f}  Brier {m['brier']:.4f}  accuracy {m['accuracy']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

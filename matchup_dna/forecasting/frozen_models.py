"""The two production models, exported once from the frozen Phase 4 procedure, and their reproduction check.

Phase 4 never saved fitted coefficients: every frozen command refitted its models from the frozen settings. For
production, the fit is done once, here, exactly as the frozen procedure specifies, and the result is written to
`models/` as JSON. Inference then reads those numbers and never refits.

    Model A  phase4-ts    P4-refit: Elo + rank + inactivity + form + opponent-adjusted serve and return,
                          fitted per tour on every rated match from 2010 to the week of 25 May 2026
                          (L2 ATP 10, WTA 0), as experiments/phase4_frozen_protocol.json specifies
    Model B  phase4-r0    R0: the same features + round-aware Elo shifts + earlier-round share of games won,
                          fitted per tour on the later-round rows of the same period (L2 ATP 100, WTA 0)

The fitting rows are those of Phase 4 erratum 1's corrected rebuild, which are identical to the original run's
(phase4_correction checks this), so the fits are the frozen procedure's fits.

`export` writes the artifacts only after three checks pass, and never overwrites an existing artifact:

1. the serialized model predicts exactly what the in-memory fitted model predicts;
2. Model A reproduces all 2,453 saved corrected held-out predictions (results/phase4/corrected/heldout_predictions.csv)
   to the file's 6-decimal rounding;
3. Model B reproduces Phase 4's published corrected round-aware score: log loss 0.5993 on 1,275 later-round
   held-out matches, against 0.6052 for its reference.

`check` refits and confirms the stored artifacts are reproduced byte for byte.

Any change to a model's definition, features, fitting rows or penalty is a new model with a new version name; the
artifacts here are never edited.
"""
import csv
import json
import platform
import sys

import numpy as np

from matchup_dna.elo import RESULTS_DIR
from matchup_dna.forecasting.records import canonical_json, sha256_text
from matchup_dna.model import mean_log_loss, sigmoid
from matchup_dna.phase4_model import design, feature_names

ROOT = RESULTS_DIR.parent
MODELS_DIR = ROOT / "models"
PHASE4_PROTOCOL = ROOT / "experiments" / "phase4_frozen_protocol.json"
ERRATUM = ROOT / "experiments" / "phase4_erratum_1.json"
CORRECTED_PREDICTIONS = RESULTS_DIR / "phase4" / "corrected" / "heldout_predictions.csv"
VERIFICATION_OUTPUT = RESULTS_DIR / "phase6" / "frozen_model_verification.txt"

TOURNAMENT_START = "tournament_start"
ROUND_AWARE = "round_aware"
SPECS = {
    TOURNAMENT_START: {"version": "phase4-ts-v1", "file": "phase4_tournament_start.json", "research_name": "P4-refit"},
    ROUND_AWARE: {"version": "phase4-r0-v1", "file": "phase4_round_aware_r0.json", "research_name": "R0"},
}
FIT_START = 20100101
PUBLISHED_R0 = {"rows": 1275, "R0": 0.5993, "reference": 0.6052}
TOLERANCE_SAVED = 5e-7      # the corrected predictions file rounds to 6 decimals


class FrozenLogistic:
    """A Phase4Logistic rebuilt from stored numbers. Same design matrix (phase4_model.design), same scaling, same
    coefficients, so it computes the same arithmetic as the fitted object."""

    def __init__(self, spec):
        self.groups = tuple(spec["groups"])
        self.preprocessing = dict(spec["preprocessing"])
        self.scale = np.array(spec["scale"], dtype=float)
        self.coefficients = np.array(spec["coefficients"], dtype=float)
        if list(spec["feature_names"]) != feature_names(self.groups):
            raise ValueError("stored feature names do not match the groups' definition in phase4_model")

    def log_odds(self, rows):
        return design(rows, self.groups, self.preprocessing) / self.scale @ self.coefficients

    def predict(self, rows):
        return sigmoid(self.log_odds(rows))

    def contributions(self, rows):
        X = design(rows, self.groups, self.preprocessing) / self.scale
        return X * self.coefficients, feature_names(self.groups)


class FrozenModel:
    """One production model: a version name, the artifact's hash, and a FrozenLogistic per tour."""

    def __init__(self, artifact_text):
        self.text = artifact_text
        self.artifact = json.loads(artifact_text)
        self.sha256 = sha256_text(artifact_text)
        self.version = self.artifact["model_version"]
        self.kind = self.artifact["kind"]
        self.tours = {tour: FrozenLogistic(spec) for tour, spec in self.artifact["tours"].items()}

    def predict(self, rows):
        p = np.empty(len(rows))
        for tour, model in self.tours.items():
            index = [i for i, row in enumerate(rows) if row["tour"] == tour]
            if index:
                p[index] = model.predict([rows[i] for i in index])
        if any(row["tour"] not in self.tours for row in rows):
            raise ValueError("a row's tour has no fitted model")
        return p

    def explain(self, row):
        """[(feature, value fed to the model, contribution to the log-odds)] for one row; contributions sum to the
        log-odds of player A winning."""
        model = self.tours[row["tour"]]
        X = design([row], model.groups, model.preprocessing)[0]
        terms = X / model.scale * model.coefficients
        return [(name, float(x), float(t)) for name, x, t in zip(feature_names(model.groups), X, terms)]


def load_models(directory=MODELS_DIR):
    """{TOURNAMENT_START: FrozenModel, ROUND_AWARE: FrozenModel} from the stored artifacts."""
    found = {}
    for kind, spec in SPECS.items():
        path = directory / spec["file"]
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing: run python -m matchup_dna.forecasting models export")
        model = FrozenModel(path.read_text(encoding="utf-8"))
        if model.version != spec["version"] or model.kind != kind:
            raise ValueError(f"{path} holds {model.version} ({model.kind}), expected {spec['version']} ({kind})")
        found[kind] = model
    return found


# ---------------------------------------------------------------- export (once) and check

def rows_sha256(rows):
    return sha256_text(canonical_json([[r["match_id"], r["a_id"], r["b_id"], r["a_won"]] for r in rows]))


def file_sha256(path):
    from matchup_dna.experiment import sha256
    return sha256(path)


def fit_frozen():
    """Refits the frozen procedure's models. Returns (protocol, fitted models by tour, fitting rows, held-out rows)."""
    from matchup_dna.phase4_experiment import HELD_OUT, PROTOCOL_PATH, fit_final_models, provider_period
    protocol = json.loads(PHASE4_PROTOCOL.read_text(encoding="utf-8"))
    rows, _, _, _ = provider_period(*HELD_OUT, unseal_with=PROTOCOL_PATH, version=2)
    fit_rows = [r for r in rows if FIT_START <= r["tourney_date"] < HELD_OUT[0]]
    held = [r for r in rows if r["tourney_date"] >= HELD_OUT[0]]
    selection = {"groups": tuple(protocol["tournament_start"]["model"]["groups"]),
                 "l2": protocol["tournament_start"]["model"]["l2"]}
    reps = protocol["tournament_start"]["model"]["representations"]
    models = fit_final_models(fit_rows, selection, reps, {
        "r0_groups": protocol["round_aware"]["R0"]["groups"], "r0_l2": protocol["round_aware"]["R0"]["l2"],
        "kept_groups": protocol["round_aware"]["kept"]["groups"], "l2": protocol["round_aware"]["kept"]["l2"]})
    return protocol, models, fit_rows, held


def artifact_text(kind, protocol, models, fit_rows):
    spec = SPECS[kind]
    tours = {}
    for tour in ("ATP", "WTA"):
        fitted = models[tour][spec["research_name"]]
        rows = [r for r in fit_rows if r["tour"] == tour and (kind == TOURNAMENT_START or r["ra_later_round"])]
        tours[tour] = {
            "groups": list(fitted.groups), "l2": fitted.l2, "representation": fitted.representation,
            "feature_names": feature_names(fitted.groups), "preprocessing": fitted.preprocessing,
            "scale": [float(x) for x in fitted.scale], "coefficients": [float(x) for x in fitted.coefficients],
            "fit_rows": len(rows), "fit_rows_sha256": rows_sha256(rows),
            "coefficients_per_feature_unit": {k: float(v) for k, v in fitted.unscaled_coefficients().items()},
        }
    description = {
        TOURNAMENT_START: "Phase 4 tournament-start model (P4-refit): uses only information from before the "
                          "tournament's start date.",
        ROUND_AWARE: "Phase 4 round-aware model (R0): the tournament-start information plus the completed earlier "
                     "rounds of the same tournament. Not a live, point-by-point model.",
    }[kind]
    payload = {
        "model_version": spec["version"],
        "kind": kind,
        "description": description,
        "research_name": spec["research_name"],
        "population": ("every rated main-draw match" if kind == TOURNAMENT_START else
                       "later-round knockout matches where at least one player has already played in the edition "
                       "and both players' earlier rounds are complete (Phase 4 Data Audit A6-A7)"),
        "fit": {"from": FIT_START, "through_week": 20260525,
                "rule": protocol["refit"]},
        "tours": tours,
        "provenance": {
            "frozen_protocol": "experiments/phase4_frozen_protocol.json",
            "frozen_protocol_sha256": file_sha256(PHASE4_PROTOCOL),
            "erratum": "experiments/phase4_erratum_1.json",
            "erratum_sha256": file_sha256(ERRATUM),
            "profile_settings_sha256": file_sha256(RESULTS_DIR / "phase4" / "profile_settings.json"),
            "feature_code": "matchup_dna/phase4_model.py, profiles.py, round_aware.py, features.py",
            "numpy": np.__version__,
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def verify(protocol, models, fit_rows, held, texts):
    """The three reproduction checks. Returns (lines, passed)."""
    from matchup_dna.model import labels
    lines, passed = [], True
    frozen = {kind: FrozenModel(text) for kind, text in texts.items()}

    for kind, spec in SPECS.items():
        target = held if kind == TOURNAMENT_START else [r for r in held if r["ra_later_round"]]
        worst = 0.0
        for tour in ("ATP", "WTA"):
            rows = [r for r in target if r["tour"] == tour]
            direct = models[tour][spec["research_name"]].predict(rows)
            stored = frozen[kind].tours[tour].predict(rows)
            worst = max(worst, float(np.max(np.abs(direct - stored))) if len(rows) else 0.0)
        ok = worst == 0.0
        passed &= ok
        lines.append(f"1. {spec['version']}: serialized model against the fitted model on {len(target):,} held-out "
                     f"rows: largest difference {worst:.1e} -> {'identical' if ok else 'DIFFERS'}")

    with open(CORRECTED_PREDICTIONS, encoding="utf-8", newline="") as file:
        saved = {row["match_id"]: row for row in csv.DictReader(file)}
    p = frozen[TOURNAMENT_START].predict(held)
    gaps = []
    for row, value in zip(held, p):
        found = saved.get(row["match_id"])
        if found is None or int(found["a_id"]) != row["a_id"]:
            gaps.append(float("inf"))
        else:
            gaps.append(abs(float(found["P4-refit"]) - value))
    worst = max(gaps) if gaps else float("inf")
    ok = len(held) == len(saved) == 2453 and worst <= TOLERANCE_SAVED
    passed &= ok
    lines.append(f"2. phase4-ts-v1 against the {len(saved):,} saved corrected held-out predictions: {len(held):,} rows, "
                 f"largest difference {worst:.1e} (file rounds to 6 decimals) -> {'reproduced' if ok else 'DIFFERS'}")

    later = [r for r in held if r["ra_later_round"]]
    y = labels(later)
    r0 = mean_log_loss(frozen[ROUND_AWARE].predict(later), y)
    reference = mean_log_loss(frozen[TOURNAMENT_START].predict(later), y)
    ok = len(later) == PUBLISHED_R0["rows"] and round(r0, 4) == PUBLISHED_R0["R0"] and \
        round(reference, 4) == PUBLISHED_R0["reference"]
    passed &= ok
    lines.append(f"3. phase4-r0-v1 on {len(later):,} later-round held-out matches: log loss {r0:.4f} (published "
                 f"{PUBLISHED_R0['R0']}), reference {reference:.4f} (published {PUBLISHED_R0['reference']}) -> "
                 f"{'reproduced' if ok else 'DIFFERS'}")
    lines.append(f"Fitting rows: {len(fit_rows):,} (2010 to the week of 25 May 2026); python {sys.version.split()[0]}, "
                 f"numpy {np.__version__}, {platform.platform()}")
    return lines, passed


def export():
    MODELS_DIR.mkdir(exist_ok=True)
    paths = {kind: MODELS_DIR / spec["file"] for kind, spec in SPECS.items()}
    if any(path.exists() for path in paths.values()):
        raise SystemExit("A model artifact already exists; artifacts are never overwritten. Use `models check` to "
                         "confirm they are reproduced.")
    protocol, models, fit_rows, held = fit_frozen()
    texts = {kind: artifact_text(kind, protocol, models, fit_rows) for kind in SPECS}
    lines, passed = verify(protocol, models, fit_rows, held, texts)
    print("\n".join(lines))
    if not passed:
        raise SystemExit("A reproduction check failed; no artifact was written.")
    for kind, path in paths.items():
        path.write_text(texts[kind], encoding="utf-8", newline="\n")
        print(f"Wrote {path} (sha256 {sha256_text(texts[kind])})")
    VERIFICATION_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    VERIFICATION_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def check():
    """Refits and confirms the stored artifacts are reproduced byte for byte, and the reproduction checks pass."""
    protocol, models, fit_rows, held = fit_frozen()
    texts = {kind: artifact_text(kind, protocol, models, fit_rows) for kind in SPECS}
    lines, passed = verify(protocol, models, fit_rows, held, texts)
    for kind, spec in SPECS.items():
        stored = (MODELS_DIR / spec["file"]).read_text(encoding="utf-8")
        same = stored == texts[kind]
        passed &= same
        lines.append(f"Stored {spec['file']} reproduced byte for byte: {same}")
    print("\n".join(lines))
    if not passed:
        raise SystemExit("The stored model artifacts are not reproduced.")

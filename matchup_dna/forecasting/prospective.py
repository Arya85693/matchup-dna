"""Prospective evaluation of the stored forecasts, under a protocol frozen before any prospective outcome exists.

    python -m matchup_dna.forecasting protocol freeze     writes experiments/phase6_prospective_protocol.json, once
    python -m matchup_dna.forecasting evaluate --monitor  the running monitor (labelled interim; decides nothing)
    python -m matchup_dna.forecasting evaluate --final    the one primary evaluation, after the window has closed

What the protocol fixes (PROTOCOL below), before the first counted forecast:

- the models (versions and artifact hashes) and the code (a hash over every file the inference path reads);
- the window: forecasts issued from the freeze, for matches scheduled up to WINDOW_END;
- which forecast counts: for each match and model, the FIRST one stored, if it was issued at least MIN_LEAD before
  the scheduled start known at the time (a later re-issue is reported as a sensitivity check, never substituted);
- which matches count: settled without conflicting reports, completed (not retired, walkover or cancelled), best of 3
  or 5. That is the research rule for a rated match;
- the metrics, the slices, the clusters for uncertainty, and the reporting rule.

Forecasts issued before the freeze (the pilot of 8 November 2026) are reported separately and never pooled.
"""
import datetime
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from matchup_dna import uncertainty
from matchup_dna.elo import RESULTS_DIR
from matchup_dna.forecasting.records import UTC, canonical_json, iso, utc

ROOT = RESULTS_DIR.parent
PROTOCOL_PATH = ROOT / "experiments" / "phase6_prospective_protocol.json"
FINAL_DIR = RESULTS_DIR / "phase6" / "prospective_final"
WINDOW_END = "2027-06-30T23:59:59Z"
EARLIEST_FINAL = "2027-07-15T00:00:00Z"
CODE_FILES = (
    "matchup_dna/forecasting/__init__.py", "matchup_dna/forecasting/records.py",
    "matchup_dna/forecasting/providers.py", "matchup_dna/forecasting/espn.py", "matchup_dna/forecasting/history.py",
    "matchup_dna/forecasting/frozen_models.py", "matchup_dna/forecasting/engine.py",
    "matchup_dna/forecasting/store.py", "matchup_dna/forecasting/pipeline.py",
    "matchup_dna/forecasting/prospective.py", "matchup_dna/features.py", "matchup_dna/phase4_features.py",
    "matchup_dna/phase4_model.py", "matchup_dna/model.py", "matchup_dna/profiles.py", "matchup_dna/round_aware.py",
    "matchup_dna/elo.py", "matchup_dna/load.py", "matchup_dna/workload.py", "matchup_dna/serve_stats.py",
    "matchup_dna/heldout.py", "matchup_dna/merge.py", "matchup_dna/crosswalk.py", "matchup_dna/tennisdata.py",
    "matchup_dna/tennisismylife.py", "matchup_dna/audit_tennisdata.py", "matchup_dna/audit_tennisismylife.py",
    "models/phase4_tournament_start.json", "models/phase4_round_aware_r0.json",
    "results/phase4/profile_settings.json",
)
BINS = 10
SEED = 20261108


def code_sha256(root=ROOT, files=CODE_FILES):
    """One hash over the inference path's files (their bytes, with line endings normalized), in a fixed order."""
    digest = hashlib.sha256()
    for name in files:
        path = Path(root) / name
        part = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() if path.exists() else "missing"
        digest.update(name.encode() + b"\0" + part.encode() + b"\n")
    return digest.hexdigest()


# ---------------------------------------------------------------- which forecasts and matches count

def counted_predictions(store, issued_from=None, issued_to=None, rule="first"):
    """{(match_uid, model_version): prediction row} under the counting rule: "first" (primary) is the first stored
    forecast; "latest" (sensitivity) is the last one issued before the scheduled start."""
    from matchup_dna.forecasting.engine import MIN_LEAD
    chosen = {}
    for row in store.predictions():
        content = json.loads(row["content_json"])
        issued = utc(row["issued_at"])
        if issued_from is not None and issued < utc(issued_from):
            continue
        if issued_to is not None and issued > utc(issued_to):
            continue
        start = utc(row["scheduled_start"])
        if start is None or issued > start - MIN_LEAD:
            continue
        key = (row["match_uid"], row["model_version"])
        if rule == "first" and key not in chosen:
            chosen[key] = dict(row, content=content)
        elif rule == "latest":
            chosen[key] = dict(row, content=content)
    return chosen


def outcome_rows(store, chosen):
    """Counted forecasts joined to settled, completed results. Returns (rows, exclusion counts)."""
    settled = store.settled()
    rows, excluded = [], Counter()
    for (uid, version), prediction in chosen.items():
        settlement = settled.get(uid)
        if settlement is None:
            excluded["no result yet"] += 1
            continue
        if settlement["state"] == "conflict":
            excluded["sources disagree on the result (left for review)"] += 1
            continue
        if settlement["status"] != "completed":
            excluded[f"not a completed match ({settlement['status']})"] += 1
            continue
        best_of = prediction["content"]["inputs"]["fixture"]["best_of"]
        if best_of not in (3, 5):
            excluded["not best of 3 or 5"] += 1
            continue
        if settlement["winner_id"] not in (prediction["player_a"], prediction["player_b"]):
            excluded["result names a player not in the forecast (identity problem)"] += 1
            continue
        content = prediction["content"]
        row = content["inputs"]["row"]
        fixture = content["inputs"]["fixture"]
        players = content["inputs"]["players"]
        ranks = [r for r in (players["a"]["rank"], players["b"]["rank"]) if r is not None]
        rows.append({
            "match_uid": uid, "model_version": version, "model_kind": content["model_kind"],
            "p": prediction["p_a"], "y": int(settlement["winner_id"] == prediction["player_a"]),
            "tour": fixture["tour"], "surface": fixture["surface"] or "unknown",
            "level": level_group(fixture["tour"], fixture["tourney_level"], fixture["tourney_name"]),
            "round": fixture["round"], "week": week_of(fixture["tourney_date"]), "edition": fixture["edition_uid"],
            "best_rank_band": rank_band(min(ranks) if ranks else None),
            "coverage": coverage_band(min(row["a_elo_matches"], row["b_elo_matches"])),
            "identity": "new player involved" if "new_player" in (players["a"]["identity"], players["b"]["identity"])
            else "both verified",
            "elo_probability": row["surface_elo_probability"],
        })
    return rows, excluded


def level_group(tour, level, name):
    if level == "G":
        return "Grand Slam"
    if level in ("M", "PM") or (tour == "WTA" and level == "1000"):
        return "Masters / WTA 1000"
    if level == "F" or "Finals" in (name or ""):
        return "Tour finals"
    if level == "D":
        return "Team event"
    return "Other tour level"


def rank_band(rank):
    if rank is None:
        return "both unranked"
    return "better player top 20" if rank <= 20 else "better player 21-100" if rank <= 100 else "better player >100"


def coverage_band(matches):
    return "less-experienced player <20 rated matches" if matches < 20 else \
        "less-experienced player 20-99" if matches < 100 else "less-experienced player 100+"


def week_of(date):
    """The Monday of the week an edition starts in: the cluster for uncertainty."""
    day = datetime.date(date // 10000, date // 100 % 100, date % 100)
    return (day - datetime.timedelta(days=day.weekday())).isoformat()


# ---------------------------------------------------------------- metrics

def match_log_loss(p, y):
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def metrics(rows):
    if not rows:
        return {"n": 0}
    p = np.array([r["p"] for r in rows])
    y = np.array([r["y"] for r in rows])
    losses = match_log_loss(p, y)
    clusters = [r["week"] for r in rows]
    mean, se = uncertainty.clustered_mean(losses, clusters)
    correct = np.where(p == 0.5, 0.5, (p > 0.5) == (y == 1))
    return {"n": len(rows), "weeks": len(set(clusters)), "log_loss": float(mean), "log_loss_se": se,
            "brier": float(np.mean((p - y) ** 2)), "accuracy": float(np.mean(correct)),
            "calibration": calibration_line(p, y), "ece": expected_calibration_error(p, y),
            "reliability": reliability(p, y)}


def reliability(p, y, bins=BINS):
    found = []
    for b in range(bins):
        low, high = b / bins, (b + 1) / bins
        mask = (p >= low) & ((p < high) if b < bins - 1 else (p <= high))
        if mask.any():
            found.append({"bin": f"{low:.1f}-{high:.1f}", "n": int(mask.sum()), "mean_p": float(p[mask].mean()),
                          "observed": float(y[mask].mean())})
    return found


def expected_calibration_error(p, y, bins=BINS):
    """Weighted mean |observed - predicted| over equal-width bins. Biased upward in small samples: read with care."""
    total = 0.0
    for entry in reliability(p, y, bins):
        total += entry["n"] * abs(entry["observed"] - entry["mean_p"])
    return total / len(p)


def calibration_line(p, y):
    """(a, b) of logit P(y) = a + b logit(p), fitted by Newton's method; (0, 1) is perfect calibration."""
    from matchup_dna.model import fit_logistic, logit
    if len(set(y.tolist())) < 2 or len(p) < 20:
        return None
    x = logit(np.clip(p, 1e-9, 1 - 1e-9)).reshape(-1, 1)
    try:
        w, a = fit_logistic(x, y, 0.0, intercept=True)
    except (np.linalg.LinAlgError, RuntimeError):
        return None
    return {"intercept": float(a), "slope": float(w[0])}


def paired(rows_new, rows_old):
    """Paired log-loss difference (new minus old) on the matches both counted, clustered by week, with a week-level
    cluster bootstrap. Matches are paired by match_uid; player A is the same in both (chosen from the match)."""
    old = {r["match_uid"]: r for r in rows_old}
    pairs = [(r, old[r["match_uid"]]) for r in rows_new if r["match_uid"] in old]
    if not pairs:
        return {"n": 0}
    diff = [float(match_log_loss([a["p"]], [a["y"]])[0] - match_log_loss([b["p"]], [b["y"]])[0]) for a, b in pairs]
    clusters = [a["week"] for a, _ in pairs]
    mean, se = uncertainty.clustered_mean(diff, clusters)
    low, high, p_value = uncertainty.interval(mean, se)
    items = list(zip(diff, clusters))
    draws = uncertainty.cluster_bootstrap(items, lambda item: item[1], lambda sample: float(np.mean([d for d, _ in sample])),
                                          seed=SEED) if len(set(clusters)) > 1 else []
    b_low, b_high = uncertainty.percentile_interval(draws) if draws else (float("nan"), float("nan"))
    return {"n": len(pairs), "weeks": len(set(clusters)), "gap": mean, "se": se, "low": low, "high": high,
            "p": p_value, "bootstrap_low": b_low, "bootstrap_high": b_high}


SLICES = ("tour", "surface", "level", "best_rank_band", "coverage", "identity", "round")


def lines_for(title, rows):
    m = metrics(rows)
    if not m["n"]:
        return [f"   {title}: no matches"]
    cal = m["calibration"]
    cal_text = f"calibration a {cal['intercept']:+.3f}, b {cal['slope']:.3f}" if cal else "calibration n/a"
    se = m["log_loss_se"]
    se_text = "n/a" if se is None or (isinstance(se, float) and math.isnan(se)) else f"{se:.4f}"
    return [f"   {title}: n {m['n']:,} ({m['weeks']} weeks)  log loss {m['log_loss']:.4f} (se {se_text})  "
            f"Brier {m['brier']:.4f}  accuracy {m['accuracy']:.2%}  {cal_text}  ECE {m['ece']:.3f}"]


def report(rows_by_kind, excluded):
    from matchup_dna.forecasting.frozen_models import ROUND_AWARE, TOURNAMENT_START
    lines = []
    for kind, rows in rows_by_kind.items():
        lines += lines_for(f"{kind} (all counted)", rows)
        if kind == TOURNAMENT_START and rows:
            benchmark = [dict(r, p=r["elo_probability"]) for r in rows]
            lines += lines_for("surface Elo, uncalibrated (descriptive benchmark)", benchmark)
        for field in SLICES:
            groups = defaultdict(list)
            for r in rows:
                groups[r[field]].append(r)
            for value in sorted(groups):
                lines += lines_for(f"{kind} by {field} = {value}", groups[value])
        if rows:
            lines.append(f"   {kind} reliability: " + "; ".join(
                f"{b['bin']} n {b['n']} p {b['mean_p']:.3f} obs {b['observed']:.3f}" for b in metrics(rows)["reliability"]))
    a, b = rows_by_kind.get(TOURNAMENT_START, []), rows_by_kind.get(ROUND_AWARE, [])
    gap = paired(b, a)
    if gap["n"]:
        lines.append(f"   R0 minus tournament start, same later-round matches: {gap['gap']:+.4f} (week-clustered se "
                     f"{gap['se']:.4f}, 95% {gap['low']:+.4f} to {gap['high']:+.4f}, p {gap['p']:.3f}; bootstrap "
                     f"{gap['bootstrap_low']:+.4f} to {gap['bootstrap_high']:+.4f}); n {gap['n']}, {gap['weeks']} weeks")
        same_a = [r for r in a if r["match_uid"] in {x["match_uid"] for x in b}]
        lines += lines_for("tournament start on those same matches", same_a)
    for key, value in sorted(excluded.items()):
        lines.append(f"   excluded: {key}: {value}")
    return lines


def rows_by_kind(store, issued_from=None, issued_to=None, rule="first"):
    rows, excluded = outcome_rows(store, counted_predictions(store, issued_from, issued_to, rule))
    found = defaultdict(list)
    for r in rows:
        found[r["model_kind"]].append(r)
    return dict(found), excluded


def score_store(store):
    """Descriptive scores for every counted forecast in a store (rehearsals and monitors)."""
    found, excluded = rows_by_kind(store)
    return report(found, excluded)


# ---------------------------------------------------------------- protocol

def protocol_contents(frozen_at):
    from matchup_dna.forecasting.engine import MIN_LEAD
    from matchup_dna.forecasting.frozen_models import load_models
    models = load_models()
    return {
        "phase": 6,
        "name": "Prospective evaluation 1 (P1)",
        "frozen_at": iso(frozen_at),
        "code_sha256": code_sha256(),
        "code_files": list(CODE_FILES),
        "models": {m.kind: {"version": m.version, "artifact_sha256": m.sha256} for m in models.values()},
        "store": "live mode only; replay stores and the 8 November 2026 pilot store are never pooled with P1",
        "window": {"issued_from": iso(frozen_at), "scheduled_up_to": WINDOW_END,
                   "final_evaluation_not_before": EARLIEST_FINAL},
        "counted_forecast": f"for each match and model, the first stored forecast, if issued at least {MIN_LEAD} before "
                            "the scheduled start known when issued; sensitivity: the last forecast before the start",
        "code_rule": "a forecast counts only if its code_sha256 equals this protocol's; a code change during the window "
                     "needs a committed amendment that lists the changed files and states that features, models and "
                     "eligibility are unchanged, else forecasts from the changed code are reported separately",
        "counted_matches": "settled with no conflicting source reports; status completed (retirements, walkovers, "
                           "defaults and cancellations excluded and counted); best of 3 or 5",
        "primary": {
            "A": "tournament-start model (phase4-ts-v1): log loss on all counted matches, ATP and WTA separately and "
                 "combined, with week-clustered standard errors",
            "B": "round-aware R0 (phase4-r0-v1) minus tournament start on the identical later-round matches where both "
                 "were counted: paired log-loss difference, week-clustered 95% interval and a week-level cluster "
                 "bootstrap (2,000 draws, seed 20261108)",
        },
        "secondary": ["Brier score", "accuracy (0.5 counts half)", "reliability in ten 0.1 bins",
                      "calibration line (intercept, slope)", "expected calibration error (descriptive only)",
                      "uncalibrated surface Elo on the same matches (descriptive benchmark)"],
        "slices": {"tour": "ATP, WTA", "surface": "Hard, Clay, Grass, Carpet, unknown",
                   "level": "Grand Slam; Masters / WTA 1000; tour finals; team events; other tour level",
                   "best_rank_band": "better-ranked player top 20, 21-100, over 100, both unranked",
                   "coverage": "less-experienced player under 20, 20-99, 100+ rated matches",
                   "identity": "both verified, or a new player involved", "round": "each round"},
        "clusters": "the Monday of the week the edition starts; both tours together, because the same week shares "
                    "conditions and data feeds. Sensitivity: clusters by edition",
        "reporting_rule": "a difference is called an improvement only if its 95% interval excludes zero; slices are "
                          "descriptive; no slice result is called a finding",
        "expected_size": "at most about 3,000 rated tournament-start matches and 1,500 later-round pairs (the "
                         "November-June calendar; June-October 2026 had 2,453 and 1,275), and only if fresh fixtures "
                         "are ingested at least daily; fewer if snapshots are less frequent. With 1,500 pairs the "
                         "standard error of the R0 gap is about 0.0025 (Phase 4 validation 0.0011 on 7,829 rows, "
                         "scaled), so the smallest gain detectable with 80% power is about 0.007, against Phase 4's "
                         "0.0054-0.0072: P1 alone may well be inconclusive for R0, and that will be said",
        "reference_values": {"tournament_start_corrected_held_out_log_loss": 0.6065,
                             "r0_minus_reference_corrected_held_out": -0.0059,
                             "note": "Phase 4 erratum 1, June-October 2026; descriptive comparison only"},
        "decisions_forbidden": "no model, feature, eligibility rule, threshold or calibration may be chosen from P1 "
                               "outcomes while P1 is described as untouched. A model changed in response to P1 is a new "
                               "version, evaluated on a later window that starts after its own freeze",
        "monitoring": "the monitor may be run at any time; its output is labelled interim, and it can trigger only an "
                      "operational fix (data, identity, ingestion), never a model change inside P1",
        "markets": "not part of P1. Market prices, if collected, are stored with their own collection timestamps and "
                   "evaluated under a separate protocol",
    }


def freeze(frozen_at=None):
    if PROTOCOL_PATH.exists():
        raise SystemExit(f"{PROTOCOL_PATH} exists; a protocol is never overwritten.")
    contents = protocol_contents(frozen_at or datetime.datetime.now(UTC))
    PROTOCOL_PATH.write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")
    print(f"Written to {PROTOCOL_PATH} (code {contents['code_sha256'][:12]}, frozen {contents['frozen_at']}).")


def load_protocol():
    if not PROTOCOL_PATH.exists():
        raise SystemExit(f"{PROTOCOL_PATH} does not exist: freeze the protocol first.")
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def evaluate(store, final=False, now=None):
    protocol = load_protocol()
    now = utc(now) if now else datetime.datetime.now(UTC)
    if store.mode != "live":
        raise SystemExit("The prospective evaluation reads a live store only.")
    if final:
        if now < utc(protocol["window"]["final_evaluation_not_before"]):
            raise SystemExit(f"The final evaluation runs on or after {protocol['window']['final_evaluation_not_before']}.")
        if FINAL_DIR.exists():
            raise SystemExit(f"{FINAL_DIR} exists: the final P1 evaluation has run.")
    chosen = counted_predictions(store, protocol["window"]["issued_from"], None, "first")
    chosen = {k: v for k, v in chosen.items()
              if utc(v["scheduled_start"]) <= utc(protocol["window"]["scheduled_up_to"])}
    wrong_code = {k for k, v in chosen.items() if v["content"].get("code_sha256") != protocol["code_sha256"]}
    wrong_model = {k for k, v in chosen.items()
                   if v["content"]["model_sha256"] not in {m["artifact_sha256"] for m in protocol["models"].values()}}
    for key in wrong_code | wrong_model:
        chosen.pop(key)
    rows, excluded = outcome_rows(store, chosen)
    excluded["issued by code other than the protocol's"] = len(wrong_code)
    excluded["issued by a model other than the protocol's"] = len(wrong_model)
    found = defaultdict(list)
    for r in rows:
        found[r["model_kind"]].append(r)
    label = "FINAL P1 EVALUATION (run once)" if final else "INTERIM MONITOR (not the P1 result; decides nothing)"
    lines = [label, f"Protocol {PROTOCOL_PATH.name} frozen {protocol['frozen_at']}; run {iso(now)}", ""]
    lines += report(dict(found), excluded)
    latest, _ = outcome_rows(store, {k: v for k, v in counted_predictions(
        store, protocol["window"]["issued_from"], None, "latest").items() if k in chosen})
    lines.append("\nSensitivity: the last forecast before the start instead of the first")
    by_kind = defaultdict(list)
    for r in latest:
        by_kind[r["model_kind"]].append(r)
    for kind, kind_rows in by_kind.items():
        lines += lines_for(f"{kind} (latest)", kind_rows)
    if final:
        FINAL_DIR.mkdir(parents=True)
        (FINAL_DIR / "evaluation.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines

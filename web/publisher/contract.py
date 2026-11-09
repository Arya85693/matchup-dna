"""Checks every snapshot file must pass before it is published. A failure stops the publish; the previous snapshot
stays live. The TypeScript side (web/lib/contract.ts) validates the same shapes again when it reads them.
"""
import math
import re

FORBIDDEN_KEYS = {"run_id", "payload_json", "inputs_json", "content_json", "artifact_json", "provider_player_id",
                  "provider_match_id", "path", "code_commit", "identity_method", "method"}
PATH_LIKE = re.compile(r"([A-Za-z]:\\|/Users/|/home/|\\Users\\|\.sqlite)")
UTC_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TIME_KEYS = {"issued_at", "start", "generated_at", "first_at", "last_at", "retrieved_at", "scheduled_start", "last"}
STATES = {"scheduled", "time_tbc", "in_progress", "postponed", "suspended", "cancelled", "result_pending",
          "result_conflict", "completed", "retired", "walkover"}


class ContractError(ValueError):
    pass


def _walk(value, where="$"):
    if isinstance(value, dict):
        for k, v in value.items():
            if k in FORBIDDEN_KEYS:
                raise ContractError(f"{where}.{k}: field is not public")
            if k in TIME_KEYS and v is not None and not (isinstance(v, str) and UTC_TIME.match(v)):
                raise ContractError(f"{where}.{k}: {v!r} is not a UTC time like 2026-11-09T05:30:00Z")
            _walk(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _walk(v, f"{where}[{i}]")
    elif isinstance(value, str):
        if PATH_LIKE.search(value):
            raise ContractError(f"{where}: looks like a file path")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ContractError(f"{where}: non-finite number")


def _probabilities(p, where):
    if not (isinstance(p, list) and len(p) == 2 and all(isinstance(x, float) and 0 < x < 1 for x in p)):
        raise ContractError(f"{where}: probabilities must be two numbers strictly between 0 and 1")
    if abs(p[0] + p[1] - 1) > 1e-12:
        raise ContractError(f"{where}: probabilities sum to {p[0] + p[1]!r}")


def check_match_summary(m, where, model_versions):
    if m["state"] not in STATES:
        raise ContractError(f"{where}.state: unknown {m['state']!r}")
    if len(m["players"]) != 2:
        raise ContractError(f"{where}.players: two players required")
    for kind, f in m["forecasts"].items():
        w = f"{where}.forecasts.{kind}"
        if f["model_version"] not in model_versions:
            raise ContractError(f"{w}: unknown model version {f['model_version']!r}")
        if f["available"]:
            _probabilities(f["p"], w)
            if f["revision"]:
                _probabilities(f["revision"]["p"], w + ".revision")
            if any(p["id"] is None for p in m["players"]):
                raise ContractError(f"{w}: a forecast needs both canonical player ids")
        elif "p" in f or not f.get("reason"):
            raise ContractError(f"{w}: an unavailable forecast carries a reason and no number")


def check_index(index, model_versions):
    _walk(index)
    for i, m in enumerate(index["matches"]):
        check_match_summary(m, f"$.matches[{i}]", model_versions)


def check_match_page(page, model_versions):
    _walk(page)
    check_match_summary(page["match"], "$.match", model_versions)
    for kind, versions in page["versions"].items():
        for i, v in enumerate(versions):
            w = f"$.versions.{kind}[{i}]"
            _probabilities(v["p"], w)
            implied = 1 / (1 + math.exp(-v["log_odds"]))
            if abs(implied - v["p"][0]) > 1e-9:
                raise ContractError(f"{w}: contributions sum to {implied!r}, stored probability {v['p'][0]!r}")
        heads = [v for v in versions if v["counted"]]
        if len(heads) > 1:
            raise ContractError(f"$.versions.{kind}: more than one counted forecast")
        summary = page["match"]["forecasts"][kind]
        if versions and summary["prediction_id"] not in {v["prediction_id"] for v in versions}:
            raise ContractError(f"$.match.forecasts.{kind}: headline forecast is not among the versions")


def check_any(document):
    _walk(document)

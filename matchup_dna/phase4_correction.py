"""Phase 4 erratum 1: diagnosis and corrected rebuild of the June-October 2026 held-out evaluation.

    python -m matchup_dna.phase4_correction diagnose   data-integrity diagnostics -> results/phase4/correction/
    python -m matchup_dna.phase4_correction reconcile  independent data-level checks of both versions' streams
    python -m matchup_dna.phase4_correction evaluate   the corrected rebuild -> results/phase4/corrected/ (runs once)
    python -m matchup_dna.phase4_correction erratum    writes experiments/phase4_erratum_1.json (never overwritten)
    python -m matchup_dna.phase4_correction check      confirms the code still matches the hashes the erratum recorded

The defect (found by the post-hoc disagreement analysis): the held-out assembly added 65 TennisData.app rows that
repeat TML matches, and resolved some players to the wrong or to two identities (heldout.py, module notes).

The corrected evaluation is RETROSPECTIVE AND POST-UNBLINDING. Every held-out outcome had been seen before the
defect was found, so it is not a new independent confirmation, and the original pre-registered result (2,518
rows, P4-refit minus P3-refit -0.0040, 95% interval -0.0081 to +0.0001) stays the result of the frozen procedure.
The rebuild changes only how provider rows become matches and players (heldout.assemble version 2). It uses the
frozen models, features, parameters, training dates, and evaluation rules; `evaluate` stops if any other code that
defines them differs from the amendment-1 commit, or if any frozen input changed.
"""
import argparse
import csv
import datetime
import json
import math
from collections import Counter, defaultdict

import numpy as np

from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import ROOT, Output, sha256

CORRECTION_DIR = RESULTS_DIR / "phase4" / "correction"
CORRECTED_DIR = RESULTS_DIR / "phase4" / "corrected"
ERRATUM_PATH = ROOT / "experiments" / "phase4_erratum_1.json"
ORIGINAL_PREDICTIONS = RESULTS_DIR / "phase4" / "final" / "heldout_predictions.csv"
SUMMARY_PATH = CORRECTED_DIR / "summary.json"
FIX_FILES = ("matchup_dna/heldout.py", "matchup_dna/phase4_experiment.py")  # the code that builds the corrected rows

# Files the correction may change. Anything else under the frozen code paths that differs from the amendment-1
# commit stops `evaluate`: features, models, parameters, and evaluation rules must be exactly as frozen.
ALLOWED_CHANGES = (
    "matchup_dna/heldout.py",               # version 2 assembly (the fix); version 1 kept unchanged
    "matchup_dna/phase4_experiment.py",     # provider_period gains `version`; frozen commands pinned to version 1
    "matchup_dna/phase4_correction.py",     # this module
    "matchup_dna/posthoc_disagreement.py",  # post-hoc analyses: original path pinned, corrected path added
    "matchup_dna/posthoc_longrun.py",
    "matchup_dna/posthoc_rank_benchmark.py",
    "tests/",
)
PUBLISHED_ORIGINAL = {"rows": 2518, "gap": -0.0040, "low": -0.0081, "high": 0.0001, "p": 0.055}


# ---------------------------------------------------------------- guards

def changed_since(commit):
    """Paths under the frozen code paths that differ from `commit` in the working tree, plus untracked ones."""
    import subprocess
    from matchup_dna.phase4_experiment import CODE_PATHS
    diff = subprocess.run(["git", "diff", "--name-only", commit, "--", *CODE_PATHS], cwd=ROOT, capture_output=True,
                          text=True).stdout.split()
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "--", *CODE_PATHS], cwd=ROOT,
                               capture_output=True, text=True).stdout.split()
    return sorted(path for path in set(diff) | set(untracked) if "__pycache__" not in path)


def check_correction_state():
    """The frozen protocol and amendment 1 committed and unchanged, every frozen input unchanged, and no code that
    defines a model, feature, parameter, or evaluation rule changed since the amendment-1 commit."""
    from matchup_dna.phase4_experiment import (
        AMENDMENT_PATH, PROTOCOL_PATH, check_inputs, frozen_code_commit, git_ok,
    )
    for path in (PROTOCOL_PATH, AMENDMENT_PATH):
        if not git_ok("ls-files", "--error-unmatch", str(path)) or not git_ok("diff", "--quiet", "HEAD", "--", str(path)):
            raise SystemExit(f"{path} must be committed and unchanged.")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    check_inputs(protocol)
    commit, amendment = frozen_code_commit(protocol)
    changed = changed_since(commit)
    outside = [path for path in changed if not any(path == allowed or (allowed.endswith("/") and path.startswith(allowed))
                                                    for allowed in ALLOWED_CHANGES)]
    if outside:
        raise SystemExit("Code that defines the frozen models, features, parameters or rules differs from the "
                         f"amendment-1 commit {commit}; the corrected rebuild refuses to run:\n" + "\n".join(outside))
    return protocol, amendment, commit, {path: sha256(ROOT / path) for path in changed if (ROOT / path).exists()}


# ---------------------------------------------------------------- shared inputs

def assembly_inputs(unseal):
    from matchup_dna import heldout
    from matchup_dna import tennisdata as td
    from matchup_dna import tennisismylife as tml
    from matchup_dna.audit_tennisdata import sackmann_overlap
    from matchup_dna.crosswalk import load_player_names
    from matchup_dna.phase4_experiment import PROTOCOL_PATH
    from matchup_dna.phase4_features import backfilled_matches
    sackmann, merge_report = backfilled_matches()
    overlap, names = sackmann_overlap(), load_player_names()
    tml_links, td_links = heldout.crosswalks(overlap, names)
    return {"sackmann": sackmann, "merge_report": merge_report, "overlap": overlap, "names": names,
            "tml_links": tml_links, "td_links": td_links,
            "excluded": heldout.excluded_tournaments(overlap, names),
            "tml_rows": tml.load_tml(unseal_with=PROTOCOL_PATH if unseal else None),
            "td_rows": td.load_provider(unseal_with=PROTOCOL_PATH if unseal else None)}


def run_assembly(inputs, start, end, version, open_only=False):
    from matchup_dna import heldout
    tml_rows = [r for r in inputs["tml_rows"] if not (open_only and r["sealed"])]
    td_rows = [r for r in inputs["td_rows"] if not (open_only and r["sealed"])]
    return heldout.assemble(tml_rows, td_rows, inputs["sackmann"], inputs["names"], inputs["tml_links"],
                            inputs["td_links"], inputs["excluded"], start, end, heldout.snapshot_day(), version=version)


def person(names, tour, sackmann_id):
    found = names.get((tour, sackmann_id))
    return f"{found['first']} {found['last']}" if found else ""


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        if not rows:
            file.write("")
            return
        fields = list(dict.fromkeys(field for row in rows for field in row))
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------- diagnose

def v1_identity(inputs, source, tour, provider_id, name):
    """How version 1 resolved a player, and by which route."""
    from matchup_dna import heldout
    resolver = heldout.NameResolver(inputs["sackmann"], inputs["names"])
    report = Counter()
    if source == "tml":
        found = heldout.resolve_tml(tour, provider_id, name, inputs["tml_links"], resolver, report)
    else:
        found = heldout.resolve_td(tour, provider_id, name, inputs["td_links"], resolver, report)
    return found, next(iter(report))


def opponent_evidence(rows, tour_of, people_of, links, overlap, window=(-3, 16)):
    """{(tour, provider id): Counter of Sackmann ids found opposite a linked opponent in a Sackmann match in the
    window and the same round}. Identity evidence that does not use the player's own name."""
    from matchup_dna.crosswalk import to_day
    by_player = defaultdict(list)
    for match in overlap:
        for side in ("winner_id", "loser_id"):
            by_player[(match["tour"], match[side])].append(match)
    votes = defaultdict(Counter)
    for row in rows:
        tour = tour_of(row)
        (first, second), day, round_name = people_of(row)
        if not round_name or round_name == "RR":
            continue  # team ties: teammates meet the same opponents in the same "round", so no evidence
        for me, other in ((first, second), (second, first)):
            opponent = links.get((tour, other))
            if opponent is None:
                continue
            for match in by_player[(tour, opponent)]:
                if round_name and match["round"] != round_name:
                    continue
                if window[0] <= (day - to_day(match["tourney_date"])).days <= window[1]:
                    votes[(tour, me)][match["loser_id"] if match["winner_id"] == opponent else match["winner_id"]] += 1
    return votes


def crosswalk_audit(inputs):
    """Crosswalk entries whose own match evidence (opponents, dates, rounds; no names; team-tie rubbers excluded)
    points elsewhere in at least 3 matches and more often than to the linked player."""
    from matchup_dna import tennisdata as td
    from matchup_dna.crosswalk import to_day
    found = []
    td_open = [r for r in inputs["td_rows"] if not r["sealed"] and td.is_main_draw(r)]
    td_votes = opponent_evidence(td_open, lambda r: r["tour"],
                                 lambda r: ((r["home_id"], r["away_id"]), r["day"], td.ROUNDS.get(r["round"])),
                                 inputs["td_links"], inputs["overlap"])
    tml_open = [r for r in inputs["tml_rows"] if not r["sealed"] and int(r["tourney_date"]) <= 20260531]
    tml_votes = opponent_evidence(tml_open, lambda r: r["tour"],
                                  lambda r: ((r["winner_id"], r["loser_id"]), to_day(int(r["tourney_date"])), r["round"]),
                                  inputs["tml_links"], inputs["overlap"])
    for source, links, votes in (("TennisData.app", inputs["td_links"], td_votes), ("TML", inputs["tml_links"], tml_votes)):
        for key, linked in sorted(links.items(), key=lambda item: tuple(map(str, item[0]))):
            counts = votes.get(key, Counter())
            if not counts:
                continue
            top, top_votes = counts.most_common(1)[0]
            if top != linked and top_votes >= 3 and top_votes > counts.get(linked, 0):
                found.append({"source": source, "tour": key[0], "provider_id": key[1], "crosswalk_sackmann_id": linked,
                              "crosswalk_name": person(inputs["names"], key[0], linked),
                              "votes_for_crosswalk_id": counts.get(linked, 0), "evidence_sackmann_id": top,
                              "evidence_name": person(inputs["names"], key[0], top), "evidence_votes": top_votes})
    return found


def sackmann_cross_tournament_repeats(matches):
    """Sackmann matches with the same pair and round in two different tournaments within 3 days."""
    from matchup_dna.crosswalk import to_day
    groups = defaultdict(list)
    for m in matches:
        groups[(m["tour"], frozenset((m["winner_id"], m["loser_id"])), m["round"])].append(m)
    found = []
    for group in groups.values():
        group.sort(key=lambda m: m["tourney_date"])
        for a, b in zip(group, group[1:]):
            if a["tourney_id"] != b["tourney_id"] and (to_day(b["tourney_date"]) - to_day(a["tourney_date"])).days <= 3:
                found.append((a["key"], b["key"]))
    return found


def duplicate_table(inputs, v1_matches, v2_report):
    """One row per TennisData.app match version 1 added that version 2 links to a TML row or holds for review."""
    from matchup_dna import heldout
    from matchup_dna.audit_tennisismylife import tml_initial_options
    from matchup_dna.crosswalk import provider_name_key
    added_v1 = {m["match_num"]: m for m in v1_matches if m["source"] == "tennisdata"}
    rows = []
    for td_row, target, same_order in v2_report["details"]["third_pass"]:
        v1 = added_v1.get(td_row["match_id"])
        if v1 is None:
            continue
        people = heldout.tml_people(target)
        if not same_order:
            people = people[::-1]
        tour = td_row["tour"]
        tml_keys = {key for keys, _ in tml_initial_options(target) for key in keys}
        record = {"tour": tour, "td_match_id": td_row["match_id"], "td_tournament": td_row["tournament"],
                  "td_day": td_row["day"].isoformat(), "td_round": heldout.td_round(td_row),
                  "tml_match": f"{target['tourney_id']}|{target['match_num']}|{target['round']}",
                  "tml_date": target["tourney_date"]}
        causes = []
        for side, (tml_id, tml_name) in zip(("home", "away"), people):
            td_id, td_name = td_row[f"{side}_id"], td_row[f"{side}_name"]
            v1_td, v1_td_route = v1_identity(inputs, "tennisdata", tour, td_id, td_name)
            v1_tml, v1_tml_route = v1_identity(inputs, "tml", tour, tml_id, tml_name)
            key = provider_name_key(td_name)
            record.update({
                f"{side}_td_name": td_name, f"{side}_td_id": td_id, f"{side}_tml_name": tml_name,
                f"{side}_tml_id": tml_id, f"{side}_v1_id_td_copy": v1_td, f"{side}_v1_route_td_copy": v1_td_route,
                f"{side}_v1_id_tml_copy": v1_tml, f"{side}_v1_route_tml_copy": v1_tml_route,
                f"{side}_td_crosswalk": inputs["td_links"].get((tour, td_id)),
                f"{side}_tml_crosswalk": inputs["tml_links"].get((tour, tml_id)),
            })
            if key is None:
                causes.append(f"{td_name}: no initial, so no name key")
            elif key not in tml_keys:
                causes.append(f"{td_name} key {key[0]}+{key[1]} is not a key of {tml_name}")
            if v1_td != v1_tml:
                causes.append(f"{td_name}: version 1 ids differ ({v1_td} via {v1_td_route} vs {v1_tml} via {v1_tml_route})")
        missing = [x for x in (record["home_td_crosswalk"], record["away_td_crosswalk"]) if x is None]
        record["pass 2 failed because"] = ("a TennisData.app id is not in its crosswalk" if missing else
                                           "a TML id is not in its crosswalk" if None in (record["home_tml_crosswalk"], record["away_tml_crosswalk"])
                                           else "the crosswalk ids name different Sackmann players")
        record["causes"] = "; ".join(causes)
        rows.append(record)
    return rows


def identity_changes(v1_matches, v2_matches, names):
    """Players whose canonical id differs between the versions in the same TML match."""
    v2_by_key = {m["key"]: m for m in v2_matches}
    changes = defaultdict(lambda: {"matches": 0})
    for m in v1_matches:
        other = v2_by_key.get(m["key"])
        if other is None or m["source"] != "tml":
            continue
        for side in ("winner", "loser"):
            if m[f"{side}_id"] != other[f"{side}_id"]:
                entry = changes[(m["tour"], m[f"{side}_name"], m[f"{side}_id"], other[f"{side}_id"])]
                entry["matches"] += 1
    return [{"tour": tour, "tml_name": name, "version_1_id": old, "version_1_sackmann_name": person(names, tour, old),
             "version_2_id": new, "version_2_sackmann_name": person(names, tour, new), "tml_matches": entry["matches"]}
            for (tour, name, old, new), entry in sorted(changes.items(), key=lambda item: -item[1]["matches"])]


def vallejo_check(inputs, out):
    """The Vallejo identities from identifiers, not name similarity."""
    from matchup_dna import tennisdata as td
    from matchup_dna.load import DATA_DIR
    out("\nVALLEJO: identities from identifiers")
    with open(DATA_DIR / "atp" / "atp_players.csv", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row["player_id"] in ("118808", "209226"):
                out(f"   Sackmann {row['player_id']}: {row['name_first']} {row['name_last']}, born {row['dob']}, "
                    f"{row['ioc']}, wikidata {row['wikidata_id'] or '-'}")
    for sackmann_id in (118808, 209226):
        played = [m for m in inputs["sackmann"] if m["tour"] == "ATP" and sackmann_id in (m["winner_id"], m["loser_id"])]
        levels = Counter(m["tourney_level"] for m in played)
        out(f"   Sackmann {sackmann_id} matches: {len(played)} ({dict(levels)}); dates "
            f"{min(m['tourney_date'] for m in played)}-{max(m['tourney_date'] for m in played)}")
        if sackmann_id == 118808:
            for m in sorted(played, key=lambda m: m["tourney_date"]):
                out(f"      {m['tourney_date']} {m['tourney_name']} {m['round']}: {m['winner_name']} d. {m['loser_name']}")
    out(f"   TML id V0DP (ATP's player code, 'Adolfo Daniel Vallejo'): TML crosswalk -> {inputs['tml_links'].get(('ATP', 'V0DP'))}")
    out(f"   TennisData.app id 424916 ('Vallejo D.'): TennisData.app crosswalk -> {inputs['td_links'].get(('ATP', '424916'))}")
    td_open = [r for r in inputs["td_rows"] if not r["sealed"] and td.is_main_draw(r)
               and "424916" in (r["home_id"], r["away_id"])]
    votes = opponent_evidence(td_open, lambda r: r["tour"],
                              lambda r: ((r["home_id"], r["away_id"]), r["day"], td.ROUNDS.get(r["round"])),
                              inputs["td_links"], inputs["overlap"])[("ATP", "424916")]
    out(f"   Opponent evidence for 424916 (Sackmann player opposite a crosswalk-linked opponent, same round, -3 to +16 "
        f"days; names not used): {dict(votes)}")


def diagnose():
    from matchup_dna.phase4_experiment import HELD_OUT, REHEARSAL
    out = Output()
    out("PHASE 4 ERRATUM 1: DATA-INTEGRITY DIAGNOSTICS (post-unblinding; nothing here changes a model)")
    inputs = assembly_inputs(unseal=True)
    v1, _, v1_report = run_assembly(inputs, *HELD_OUT, version=1)
    v2, _, v2_report = run_assembly(inputs, *HELD_OUT, version=2)
    out("\nHELD-OUT ASSEMBLY, editions starting 2026-06-01 to 2026-11-04")
    out(f"   {'count':<80} {'version 1':>10} {'version 2':>10}")
    for key in sorted(set(v1_report) | set(v2_report)):
        if key in ("review", "details"):
            continue
        out(f"   {key:<80} {v1_report.get(key, '-')!s:>10} {v2_report.get(key, '-')!s:>10}")
    td_v1 = {m["match_num"] for m in v1 if m["source"] == "tennisdata"}
    td_v2 = {m["match_num"] for m in v2 if m["source"] == "tennisdata"}
    out(f"   Matches: version 1 {len(v1):,} ({len(td_v1)} from TennisData.app); version 2 {len(v2):,} "
        f"({len(td_v2)} from TennisData.app). Removed: {len(td_v1 - td_v2)}; added: {len(td_v2 - td_v1)}")

    table = duplicate_table(inputs, v1, v2_report)
    write_csv(CORRECTION_DIR / "duplicates.csv", table)
    out(f"\nDUPLICATES: {len(table)} TennisData.app rows that version 1 added and version 2 links to a TML row "
        f"(full table: {CORRECTION_DIR / 'duplicates.csv'})")
    patterns = Counter()
    for record in table:
        for side in ("home", "away"):
            if record[f"{side}_v1_id_td_copy"] != record[f"{side}_v1_id_tml_copy"]:
                patterns[(record["tour"], record[f"{side}_td_name"], record[f"{side}_td_id"], record[f"{side}_tml_name"],
                          record[f"{side}_tml_id"], record[f"{side}_v1_id_td_copy"], record[f"{side}_v1_route_td_copy"],
                          record[f"{side}_v1_id_tml_copy"], record[f"{side}_v1_route_tml_copy"])] += 1
    out("   Players behind them (version 1 gave the two copies different ids):")
    for (tour, td_name, td_id, tml_name, tml_id, a, a_route, b, b_route), count in patterns.most_common():
        out(f"   {tour} {td_name!r} (TennisData.app {td_id}) = {tml_name!r} (TML {tml_id}): {count} matches; "
            f"TD copy -> {a} [{a_route}] {person(inputs['names'], tour, a)!r}; TML copy -> {b} [{b_route}] "
            f"{person(inputs['names'], tour, b)!r}")
    out("   Why pass 2 (validated ids) missed them: " + ", ".join(
        f"{reason} {n}" for reason, n in Counter(r["pass 2 failed because"] for r in table).items()))
    leftover = sorted(td_v1 - td_v2 - {r["td_match_id"] for r in table})
    if leftover:
        out(f"   Other TennisData.app rows version 1 added and version 2 does not: {leftover}")

    changes = identity_changes(v1, v2, inputs["names"])
    write_csv(CORRECTION_DIR / "identity_changes.csv", changes)
    out(f"\nIDENTITIES: players in TML matches whose canonical id changed ({len(changes)})")
    for c in changes:
        out(f"   {c['tour']} {c['tml_name']}: {c['version_1_id']} {c['version_1_sackmann_name']!r} -> {c['version_2_id']} "
            f"{c['version_2_sackmann_name']!r} in {c['tml_matches']} TML matches")

    review = v2_report["review"]
    write_csv(CORRECTION_DIR / "review_players.csv", [{k: str(v) for k, v in r.items()} for r in review["players"]])
    write_csv(CORRECTION_DIR / "review_matches.csv", [{k: str(v) for k, v in r.items()} for r in review["possible duplicates left out"]])
    out(f"\nREVIEW (version 2 never merges these automatically): {len(review['possible duplicates left out'])} "
        f"possible duplicates left out; {len(review['players'])} player cases")
    for kind, n in Counter(r["kind"] for r in review["players"]).most_common():
        out(f"   {kind}: {n}")
    for r in review["players"]:
        if r["kind"].startswith("conflict") or r["kind"].startswith("resolved through"):
            out(f"   {r}")
    for r in review["possible duplicates left out"]:
        out(f"   {r}")

    vallejo_check(inputs, out)

    out("\nELSEWHERE")
    rv1, _, _ = run_assembly(inputs, *REHEARSAL, version=1, open_only=True)
    rv2, _, rr2 = run_assembly(inputs, *REHEARSAL, version=2, open_only=True)
    r_td1 = {m["match_num"] for m in rv1 if m["source"] == "tennisdata"}
    r_td2 = {m["match_num"] for m in rv2 if m["source"] == "tennisdata"}
    out(f"   Rehearsal window (January-May 2026, open rows; used only for outcome-free comparisons before the freeze): "
        f"version 1 added {len(r_td1)} TennisData.app rows, version 2 {len(r_td2)}; {len(r_td1 - r_td2)} were duplicates "
        f"of TML rows; identity changes in TML matches: {len(identity_changes(rv1, rv2, inputs['names']))} players")
    repeats = sackmann_cross_tournament_repeats(inputs["sackmann"])
    out(f"   Sackmann (Phases 1-4 training, validation, retrospective): same pair and round in two tournaments within "
        f"3 days: {len(repeats)}" + (f" e.g. {repeats[:3]}" if repeats else ""))
    out(f"   TML backfill of Sackmann statistics (pre-June 2026): {inputs['merge_report']}")
    audit = crosswalk_audit(inputs)
    write_csv(CORRECTION_DIR / "crosswalk_audit.csv", audit)
    out(f"   Crosswalk entries contradicted by their own match evidence (opponents, dates, rounds; names not used): "
        f"{len(audit)}")
    for entry in audit:
        out(f"      {entry}")
    CORRECTION_DIR.mkdir(parents=True, exist_ok=True)
    (CORRECTION_DIR / "diagnostics.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    summary = {"held_out": {"version_1_matches": len(v1), "version_2_matches": len(v2),
                            "version_1_tennisdata": len(td_v1), "version_2_tennisdata": len(td_v2),
                            "duplicates": len(table), "identity_changes": len(changes),
                            "review_matches": len(review["possible duplicates left out"]),
                            "review_players": dict(Counter(r["kind"] for r in review["players"]))},
               "rehearsal": {"version_1_tennisdata": len(r_td1), "version_2_tennisdata": len(r_td2),
                             "duplicates": len(r_td1 - r_td2)},
               "sackmann_cross_tournament_repeats": len(repeats), "crosswalk_audit": audit}
    (CORRECTION_DIR / "diagnostics.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\nWritten to {CORRECTION_DIR}")


# ---------------------------------------------------------------- independent reconciliation

def surname_tokens(name):
    """The possible surname tokens of a name: for "Surname I." names every token that is not an initial, for full
    names every token after the first given name ("Adolfo Daniel Vallejo" -> daniel, vallejo). Deliberately
    simpler than the matching rule in heldout.py, so this check does not inherit its logic. Names written surname
    first ("Bu Yunchaokete") can raise a false alarm, which is listed for review, never acted on."""
    from matchup_dna.crosswalk import normalize
    tokens = (name or "").replace("-", " ").split()
    if any(token.endswith(".") for token in tokens):
        kept = [token for token in tokens if not token.endswith(".")]
    else:
        kept = tokens[1:] if len(tokens) > 1 else tokens
    return {normalize(token) for token in kept if len(normalize(token)) >= 2}


def schedule_clashes(matches, days=3):
    """A player in two different tournaments whose dates are within `days` of each other: one week's tournament
    entered twice under two keys, the footprint of a duplicate whose ids agree on at least one side."""
    from matchup_dna.crosswalk import to_day
    editions = defaultdict(set)
    for m in matches:
        for side in ("winner_id", "loser_id"):
            editions[(m["tour"], m[side])].add((m["tourney_date"], m["tourney_id"]))
    found = []
    for player, held in editions.items():
        ordered = sorted(held)
        for (d1, t1), (d2, t2) in zip(ordered, ordered[1:]):
            if t1 != t2 and (to_day(d2) - to_day(d1)).days <= days:
                found.append({"tour": player[0], "player": player[1], "first": (t1, d1), "second": (t2, d2)})
    return found


def repeated_rounds(matches):
    """A player twice in one knockout round of one tournament."""
    counts = Counter((m["tour"], m[side], m["tourney_id"], m["round"]) for m in matches
                     for side in ("winner_id", "loser_id") if m["round"] not in ("RR", "unknown"))
    return [{"tour": k[0], "player": k[1], "tourney_id": k[2], "round": k[3], "count": n} for k, n in counts.items() if n > 1]


def identity_names(matches):
    """(ids whose recorded names share no surname token: possible wrong merges, ids sharing one exact full name:
    possible split identities)."""
    from matchup_dna.crosswalk import normalize
    names = defaultdict(set)
    for m in matches:
        for side in ("winner", "loser"):
            names[(m["tour"], m[f"{side}_id"])].add(m[f"{side}_name"])
    mixed = []
    for player, held in names.items():
        tokens = [surname_tokens(name) for name in held]
        if any(not (a & b) for i, a in enumerate(tokens) for b in tokens[i + 1:]):
            mixed.append({"tour": player[0], "player": player[1], "names": sorted(held)})
    by_name = defaultdict(set)
    for (tour, player), held in names.items():
        for name in held:
            if not name.rstrip().endswith("."):  # full names only; abbreviated names are not unique
                by_name[(tour, normalize(name))].add(player)
    split = [{"tour": tour, "name": name, "ids": sorted(ids)} for (tour, name), ids in by_name.items() if len(ids) > 1]
    return mixed, split


def sackmann_overlaps(matches, sackmann, start, days=14):
    """Held-out matches whose pair and round Sackmann already holds within `days` before the window."""
    from matchup_dna.crosswalk import to_day
    recent = defaultdict(list)
    for m in sackmann:
        if m["tourney_date"] >= start - 10000:
            recent[(m["tour"], frozenset((m["winner_id"], m["loser_id"])), m["round"])].append(m["tourney_date"])
    return [m["key"] for m in matches
            if any(abs((to_day(m["tourney_date"]) - to_day(d)).days) <= days
                   for d in recent.get((m["tour"], frozenset((m["winner_id"], m["loser_id"])), m["round"]), ()))]


def reconcile_stream(matches, report, sackmann, start):
    mixed, split = identity_names(matches)
    td_rows = report["TennisData.app main-draw rows in the window"]
    accounted = (report.get("TennisData.app rows matched to TML rows", 0)
                 + report.get("TennisData.app rows without a usable result (canceled, awarded, blank)", 0)
                 + report.get("TennisData.app rows added (no TML row)", 0)
                 + report.get("TennisData.app rows dropped as duplicates of TML rows by player ids", 0)
                 + report.get("TennisData.app rows left out for review (possible duplicates, not merged)", 0))
    return {"matches": len(matches), "schedule_clashes": schedule_clashes(matches),
            "repeated_rounds": repeated_rounds(matches), "ids_with_unrelated_names": mixed,
            "full_names_with_several_ids": split, "sackmann_overlaps": sackmann_overlaps(matches, sackmann, start),
            "tennisdata_rows": td_rows, "tennisdata_rows_accounted_for": accounted,
            "linked_pairs_same_winner": [report.get("data check: TML and TennisData.app name the same winner"),
                                         report.get("data check: matched pairs with a winner in both")]}


def reconcile():
    """Independent data-level check of the assembled held-out stream, for both versions."""
    from matchup_dna.phase4_experiment import HELD_OUT
    out = Output()
    out("PHASE 4 ERRATUM 1: INDEPENDENT DATA-LEVEL RECONCILIATION (canonical ids, dates and rounds; plain surname")
    out("tokens; none of the version-2 matching rules)")
    inputs = assembly_inputs(unseal=True)
    found = {}
    for version in (1, 2):
        matches, _, report = run_assembly(inputs, *HELD_OUT, version=version)
        result = reconcile_stream(matches, report, inputs["sackmann"], HELD_OUT[0])
        found[f"version_{version}"] = result
        out(f"\nVERSION {version}: {result['matches']:,} matches")
        out(f"   TennisData.app rows in the window {result['tennisdata_rows']:,}; accounted for exactly once: "
            f"{result['tennisdata_rows_accounted_for']:,}")
        out(f"   Linked pairs naming the same winner: {result['linked_pairs_same_winner'][0]} of "
            f"{result['linked_pairs_same_winner'][1]}")
        for key, label in (("schedule_clashes", "player in two tournaments within 3 days"),
                           ("repeated_rounds", "player twice in one knockout round"),
                           ("ids_with_unrelated_names", "one id, names with no surname in common"),
                           ("full_names_with_several_ids", "one exact full name, several ids"),
                           ("sackmann_overlaps", "pair and round already in Sackmann within 14 days")):
            out(f"   {label}: {len(result[key])}")
            for item in result[key][:40]:
                out(f"      {item}")
    CORRECTION_DIR.mkdir(parents=True, exist_ok=True)
    (CORRECTION_DIR / "reconciliation.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    (CORRECTION_DIR / "reconciliation.json").write_text(json.dumps(found, indent=2, default=str), encoding="utf-8")
    print(f"\nWritten to {CORRECTION_DIR / 'reconciliation.txt'}")


# ---------------------------------------------------------------- evaluate

def winner_p(p, y):
    return np.where(y == 1, p, 1 - p)


def credit(p, y):
    w = winner_p(p, y)
    return np.where(w > 0.5, 1.0, np.where(w == 0.5, 0.5, 0.0))


def paired(p_new, p_old, y, rows):
    """The paired log-loss gap with both of the protocol's clusterings: tournament date (primary) and month."""
    from matchup_dna.experiment import paired_gap
    from matchup_dna.phase4_experiment import month_gap
    weeks = np.array([r["tourney_date"] for r in rows])
    gap, se = paired_gap(p_new, p_old, y, weeks)
    _, month_se = month_gap(p_new, p_old, y, rows)
    return {"rows": len(rows), "dates": int(len(set(weeks.tolist()))), "gap": gap, "se": se, "low": gap - 1.96 * se,
            "high": gap + 1.96 * se, "p": math.erfc(abs(gap / se) / math.sqrt(2)), "month_se": month_se,
            "month_low": gap - 1.96 * month_se, "month_high": gap + 1.96 * month_se,
            "month_p": math.erfc(abs(gap / month_se) / math.sqrt(2))}


def summary_of(rows, predictions, models_by_name):
    """Scores, paired gaps (date- and month-clustered), ATP/WTA, calibration, round-aware, ranking benchmark, and
    disagreements for one version."""
    from matchup_dna.experiment import scores
    from matchup_dna.model import labels
    from matchup_dna.selection import calibration_line
    y = labels(rows)
    tours = np.array([r["tour"] for r in rows])
    p3, p4 = predictions["P3-refit"], predictions["P4-refit"]
    found = {"rows": len(rows), "scores": {}, "gaps": {}, "calibration": {}}
    for name, p in predictions.items():
        found["scores"][name] = scores(p, y)
        found["calibration"][name] = dict(zip(("intercept", "slope"), calibration_line(p, y)))
    for label, mask in (("Both", np.ones(len(rows), bool)), ("ATP", tours == "ATP"), ("WTA", tours == "WTA")):
        subset = [r for r, keep in zip(rows, mask) if keep]
        found["gaps"][label] = dict(paired(p4[mask], p3[mask], y[mask], subset),
                                    P3=scores(p3[mask], y[mask]), P4=scores(p4[mask], y[mask]))
    ra = np.array([bool(r["ra_later_round"]) for r in rows])
    if "R0" in models_by_name:
        r0, ref = models_by_name["R0"], models_by_name["ra_reference"]
        ra_rows, ra_y = [r for r in rows if r["ra_later_round"]], y[ra]
        ra_tours = tours[ra]
        found["round_aware"] = dict(paired(r0, ref, ra_y, ra_rows), R0=scores(r0, ra_y), reference=scores(ref, ra_y))
        for label in ("ATP", "WTA"):
            mask = ra_tours == label
            found["round_aware"][label] = dict(
                paired(r0[mask], ref[mask], ra_y[mask], [r for r, keep in zip(ra_rows, mask) if keep]),
                R0=scores(r0[mask], ra_y[mask]), reference=scores(ref[mask], ra_y[mask]))
    eligible = np.array([r["a_rank"] is not None and r["b_rank"] is not None and r["a_rank"] != r["b_rank"] for r in rows])
    higher = np.array([(r["a_rank"] < r["b_rank"]) == bool(r["a_won"]) if e else False for r, e in zip(rows, eligible)])
    found["ranking"] = {"eligible": int(eligible.sum()), "missing_or_tied": int((~eligible).sum()),
                        "higher_ranked_correct": int(higher[eligible].sum()),
                        "P3_correct": float(credit(p3, y)[eligible].sum()), "P4_correct": float(credit(p4, y)[eligible].sum())}
    pick3 = np.sign(p3 - 0.5)
    pick4 = np.sign(p4 - 0.5)
    disagree = (pick3 != pick4) & (pick3 != 0) & (pick4 != 0)
    found["disagreements"] = {"count": int(disagree.sum()), "share": float(disagree.mean()),
                              "P3_right": float(credit(p3, y)[disagree].sum()), "P4_right": float(credit(p4, y)[disagree].sum()),
                              "exact_half": int(((pick3 == 0) | (pick4 == 0)).sum())}
    return found


def changed_columns(old, new):
    from matchup_dna.phase4_model import GROUP_COLUMNS  # noqa: F401  (documentation: columns derive from these)
    fields = ("tourney_date", "a_id", "b_id", "a_elo", "b_elo", "a_surface_elo_blended", "b_surface_elo_blended",
              "a_rank", "b_rank", "a_days_since", "b_days_since", "a_form", "b_form", "a_serve_adjusted",
              "b_serve_adjusted", "a_return_adjusted", "b_return_adjusted", "a_serve_attempts", "b_serve_attempts",
              "overlap_flag")
    return [f for f in fields if old.get(f) != new.get(f)]


def reason_for(old, new, touched_players):
    if {old["a_id"], old["b_id"]} != {new["a_id"], new["b_id"]}:
        return "a player's identity was corrected"
    if old["tourney_date"] != new["tourney_date"]:
        return "the edition date was corrected (now linked to its TennisData.app edition)"
    if {old["a_id"], old["b_id"]} & touched_players:
        return "a player's own earlier history changed (a duplicate removed or an identity merged)"
    return "an earlier opponent's or opponent's opponent's rating or profile changed (knock-on through the rating network)"


def evaluate():
    from matchup_dna.model import LogisticModel, labels
    from matchup_dna.phase4_experiment import (
        HELD_OUT, PROTOCOL_PATH, fit_final_models, predict, provider_period, score_period,
    )
    from matchup_dna.phase4_model import PHASE3_GROUPS
    protocol, amendment, commit, changed_hashes = check_correction_state()
    if CORRECTED_DIR.exists():
        raise SystemExit(f"{CORRECTED_DIR} exists: the corrected rebuild has run. It is never silently regenerated.")
    out = Output()
    out("PHASE 4 ERRATUM 1: CORRECTED HELD-OUT EVALUATION, JUNE-OCTOBER 2026")
    out("RETROSPECTIVE AND POST-UNBLINDING. Every held-out outcome had been seen before this rebuild, so it is not a new")
    out("independent confirmation. The pre-registered result of the frozen procedure stays the original run (2,518 rows,")
    out("P4-refit minus P3-refit -0.0040, 95% interval -0.0081 to +0.0001, p 0.055). Only the provider assembly differs")
    out(f"(heldout.assemble version 2); models, features, parameters, training dates and rules are the frozen ones (code")
    out(f"checked against the amendment-1 commit {commit}). Changed files: {sorted(changed_hashes)}")

    v1_rows, _, _, _ = provider_period(*HELD_OUT, unseal_with=PROTOCOL_PATH, version=1)
    v2_rows, _, report, _ = provider_period(*HELD_OUT, unseal_with=PROTOCOL_PATH, version=2)
    fit_v1 = [r for r in v1_rows if 20100101 <= r["tourney_date"] < HELD_OUT[0]]
    fit_rows = [r for r in v2_rows if 20100101 <= r["tourney_date"] < HELD_OUT[0]]
    if [r["match_id"] for r in fit_v1] != [r["match_id"] for r in fit_rows]:
        raise SystemExit("The fitting rows differ between the versions; the correction must not touch them.")
    held_v1 = [r for r in v1_rows if r["tourney_date"] >= HELD_OUT[0]]
    held = [r for r in v2_rows if r["tourney_date"] >= HELD_OUT[0]]
    out(f"\nModels refitted, exactly as the frozen procedure, on {len(fit_rows):,} matches from 2010 to the week of "
        f"25 May 2026 (identical rows in both versions).")
    for key, value in report.items():
        if key not in ("review", "details"):
            out(f"   {key}: {value}")
    selection = {"groups": tuple(protocol["tournament_start"]["model"]["groups"]), "l2": protocol["tournament_start"]["model"]["l2"]}
    reps = protocol["tournament_start"]["model"]["representations"]
    models = fit_final_models(fit_rows, selection, reps, {
        "r0_groups": protocol["round_aware"]["R0"]["groups"], "r0_l2": protocol["round_aware"]["R0"]["l2"],
        "kept_groups": protocol["round_aware"]["kept"]["groups"], "l2": protocol["round_aware"]["kept"]["l2"]})
    p3_original = {}
    for tour, l2 in protocol["tournament_start"]["baseline"]["l2"].items():
        p3_original[tour] = LogisticModel(PHASE3_GROUPS, l2).fit(
            [r for r in fit_rows if r["tour"] == tour and r["tourney_date"] < 20240101])

    def original_model(rows):
        p = np.empty(len(rows))
        for tour, model in p3_original.items():
            index = [i for i, r in enumerate(rows) if r["tour"] == tour]
            if index:
                p[index] = model.predict([rows[i] for i in index])
        return p

    # Reproduction check: the same fitted models on the version-1 rows must give the saved original predictions.
    with open(ORIGINAL_PREDICTIONS, encoding="utf-8", newline="") as file:
        saved = {row["match_id"]: row for row in csv.DictReader(file)}
    v1_predictions = {"P3-refit": predict(models, held_v1, "P3-refit"), "P4-refit": predict(models, held_v1, "P4-refit"),
                      "P3-original": original_model(held_v1)}
    worst = max(abs(float(saved[r["match_id"]][name]) - v1_predictions[name][i])
                for i, r in enumerate(held_v1) for name in v1_predictions)
    if len(held_v1) != len(saved) or worst > 5e-7:
        raise SystemExit(f"The version-1 rebuild does not reproduce the saved original predictions (max difference {worst}).")
    out(f"\nReproduction check: version-1 rows with the same fitted models reproduce all {len(saved):,} saved original "
        f"predictions (largest difference {worst:.1e}, within the 6-decimal rounding of the file).")

    predictions = score_period(out, "Corrected held-out June-October 2026 (retrospective, post-unblinding)", held,
                               models, {"P3-original": original_model(held)})
    out(f"\nPre-registered minimum detectable gains (for reference only; this rebuild is not the pre-registered test): "
        f"{json.dumps(protocol['minimum_detectable_gain'])}")

    ra_v1 = [r for r in held_v1 if r["ra_later_round"]]
    ra_v2 = [r for r in held if r["ra_later_round"]]
    original = summary_of(held_v1, v1_predictions, {"R0": predict(models, ra_v1, "R0"),
                                                    "ra_reference": predict(models, ra_v1, "P4-refit")})
    corrected = summary_of(held, predictions, {"R0": predict(models, ra_v2, "R0"),
                                               "ra_reference": predict(models, ra_v2, "P4-refit")})
    def gap_text(g):
        return (f"{g['gap']:+.4f} (date-clustered se {g['se']:.4f}, {g['low']:+.4f} to {g['high']:+.4f}, p {g['p']:.3f}; "
                f"month-clustered se {g['month_se']:.4f}, {g['month_low']:+.4f} to {g['month_high']:+.4f}, "
                f"p {g['month_p']:.3f})")

    out("\nORIGINAL (version 1, as published) AGAINST CORRECTED (version 2)")
    for label in ("Both", "ATP", "WTA"):
        a, b = original["gaps"][label], corrected["gaps"][label]
        out(f"   {label}: rows {a['rows']:,} -> {b['rows']:,} (tournament dates {a['dates']} -> {b['dates']}); "
            f"P3 {a['P3']['log_loss']:.4f} -> {b['P3']['log_loss']:.4f}, P4 {a['P4']['log_loss']:.4f} -> "
            f"{b['P4']['log_loss']:.4f}")
        out(f"      gap original {gap_text(a)}")
        out(f"      gap corrected {gap_text(b)}")
    for name in ("P3-refit", "P4-refit", "P3-original"):
        a, b = original["scores"][name], corrected["scores"][name]
        ca, cb = original["calibration"][name], corrected["calibration"][name]
        out(f"   {name}: log loss {a['log_loss']:.4f} -> {b['log_loss']:.4f}; Brier {a['brier']:.4f} -> {b['brier']:.4f}; "
            f"accuracy {a['accuracy']:.2%} -> {b['accuracy']:.2%}; calibration intercept {ca['intercept']:+.3f} -> "
            f"{cb['intercept']:+.3f}, slope {ca['slope']:.3f} -> {cb['slope']:.3f}")
    for label in (None, "ATP", "WTA"):
        a = original["round_aware"] if label is None else original["round_aware"][label]
        b = corrected["round_aware"] if label is None else corrected["round_aware"][label]
        out(f"   Round-aware R0 against its reference (P4-refit), {label or 'Both'}: rows {a['rows']:,} -> {b['rows']:,}; "
            f"reference {a['reference']['log_loss']:.4f} -> {b['reference']['log_loss']:.4f}, R0 "
            f"{a['R0']['log_loss']:.4f} -> {b['R0']['log_loss']:.4f}; R0 accuracy {a['R0']['accuracy']:.2%} -> "
            f"{b['R0']['accuracy']:.2%}, Brier {a['R0']['brier']:.4f} -> {b['R0']['brier']:.4f}")
        out(f"      gap original {gap_text(a)}")
        out(f"      gap corrected {gap_text(b)}")
    for version, s in (("original", original), ("corrected", corrected)):
        k = s["ranking"]
        out(f"   Ranking benchmark ({version}): {k['eligible']:,} eligible ({k['missing_or_tied']} missing or tied); "
            f"higher-ranked {k['higher_ranked_correct']:,} ({k['higher_ranked_correct'] / k['eligible']:.2%}), "
            f"P3 {k['P3_correct']:g} ({k['P3_correct'] / k['eligible']:.2%}), P4 {k['P4_correct']:g} "
            f"({k['P4_correct'] / k['eligible']:.2%})")
        d = s["disagreements"]
        out(f"   Disagreements ({version}): {d['count']} ({d['share']:.2%}); Phase 3 right {d['P3_right']:g}, "
            f"Phase 4 right {d['P4_right']:g}; exact 0.5: {d['exact_half']}")

    # Which predictions changed, and why.
    old_by_id = {r["match_id"]: (r, i) for i, r in enumerate(held_v1)}
    new_ids = {r["match_id"] for r in held}
    touched = set()
    for change in identity_changes_from_rows(held_v1, held):
        touched |= change
    removed = [r for r in held_v1 if r["match_id"] not in new_ids]
    for r in removed:
        touched |= {r["a_id"], r["b_id"]}
    reasons, columns, comparison = Counter(), Counter(), []
    for i, new in enumerate(held):
        found = old_by_id.get(new["match_id"])
        record = {"match_id": new["match_id"], "tour": new["tour"], "tourney_date": new["tourney_date"],
                  "a_id": new["a_id"], "b_id": new["b_id"], "a_won": new["a_won"],
                  "P3-refit": f"{predictions['P3-refit'][i]:.6f}", "P4-refit": f"{predictions['P4-refit'][i]:.6f}"}
        if found is None:
            record["status"] = "new in version 2"
        else:
            old, j = found
            # Compared as the probability given to the actual winner: a corrected identity can swap players A and B.
            def to_winner(p, a_won):
                return p if a_won else 1 - p
            moved = max(abs(to_winner(predictions[n][i], new["a_won"]) - to_winner(v1_predictions[n][j], old["a_won"]))
                        for n in ("P3-refit", "P4-refit"))
            for n in ("P3-refit", "P4-refit"):
                record[f"{n} P(winner)"] = f"{to_winner(predictions[n][i], new['a_won']):.6f}"
                record[f"original {n} P(winner)"] = f"{to_winner(v1_predictions[n][j], old['a_won']):.6f}"
            if moved < 1e-12:
                record["status"] = "unchanged"
            else:
                record["status"] = "changed"
                record["reason"] = reason_for(old, new, touched)
                record["largest_change"] = f"{moved:.6f}"
                record["changed_columns"] = " ".join(changed_columns(old, new))
                reasons[record["reason"]] += 1
                columns.update(changed_columns(old, new))
        comparison.append(record)
    status = Counter(r["status"] for r in comparison)
    big = sorted((r for r in comparison if r["status"] == "changed"), key=lambda r: -float(r["largest_change"]))
    out(f"\nPREDICTIONS: {len(removed)} original rows removed (duplicate copies); of the {len(held):,} corrected rows: "
        + ", ".join(f"{k} {v:,}" for k, v in status.items()))
    for reason, n in reasons.most_common():
        out(f"   changed because {reason}: {n:,}")
    out("   Columns that changed (count of matches): " + ", ".join(f"{c} {n}" for c, n in columns.most_common()))
    changes = np.array([float(r["largest_change"]) for r in big])
    if len(changes):
        out(f"   Size of the change in the probability given to the actual winner (larger of P3 and P4): median "
            f"{np.median(changes):.4f}, "
            f"90th percentile {np.quantile(changes, 0.9):.4f}, largest {changes.max():.4f}; "
            f"over 0.01 on {(changes > 0.01).sum()} matches")

    CORRECTED_DIR.mkdir(parents=True)
    with open(CORRECTED_DIR / "heldout_predictions.csv", "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["match_id", "tourney_date", "tour", "a_id", "b_id", "a_won"] + list(predictions))
        for i, row in enumerate(held):
            writer.writerow([row["match_id"], row["tourney_date"], row["tour"], row["a_id"], row["b_id"], row["a_won"]]
                            + [f"{predictions[name][i]:.6f}" for name in predictions])
    write_csv(CORRECTED_DIR / "prediction_changes.csv", comparison)
    write_csv(CORRECTED_DIR / "removed_rows.csv", [{"match_id": r["match_id"], "tour": r["tour"],
                                                    "tourney_date": r["tourney_date"]} for r in removed])
    payload = {"created": datetime.date.today().isoformat(), "label": "retrospective, post-unblinding correction",
               "code_checked_against": commit, "changed_files_sha256": changed_hashes,
               "original": original, "corrected": corrected, "removed_rows": len(removed),
               "prediction_status": dict(status), "change_reasons": dict(reasons),
               "review": report.get("review")}
    SUMMARY_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (CORRECTED_DIR / "evaluation.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    print(f"\nWritten to {CORRECTED_DIR}")


def identity_changes_from_rows(old_rows, new_rows):
    """Sets of player ids involved where a match keeps its id but a player's canonical id changed."""
    new_by_id = {r["match_id"]: r for r in new_rows}
    for old in old_rows:
        new = new_by_id.get(old["match_id"])
        if new is not None and {old["a_id"], old["b_id"]} != {new["a_id"], new["b_id"]}:
            yield {old["a_id"], old["b_id"], new["a_id"], new["b_id"]}


# ---------------------------------------------------------------- erratum record

ERRATUM_DEFECT = (
    "Found after unblinding, by the post-hoc disagreement analysis (2026-11-05). The held-out assembly "
    "(heldout.assemble, version 1) added a TennisData.app row unless it linked to a TML row by matching "
    "surname-and-initial keys for both players, or by both players being in both validated crosswalks; its last guard "
    "compared resolved player ids. Players whose providers write their names differently ('Merida Aguilar D.' / "
    "'Daniel Merida', 'Ruse G.' / 'Elena Gabriela Ruse', 'Vallejo D.' / 'Adolfo Daniel Vallejo', 'Tam Sin Hang' / "
    "'Sin Hang Tam', ...) failed every check and were resolved to different ids, so 65 matches were added twice and "
    "updated ratings, form, inactivity and profiles twice. The TennisData.app crosswalk also linked 'Vallejo D.' "
    "(424916) to Sackmann 118808 (Daniel Vallejo, MEX, born 1984) instead of 209226 (Adolfo Daniel Vallejo, PAR, born "
    "2004), because Sackmann files Paraguay's 2023-2026 Davis Cup matches under 118808; and TML's 'Daniel Merida' "
    "(M0N7) had no link, so his TML matches started from a new, history-less identity.")
ERRATUM_FIX = (
    "heldout.assemble version 2 (version 1 kept for reproduction): a third match-linking pass on round, edition, "
    "dates and name-compatible players (never on results), with ambiguous cases left out and listed; TennisData.app "
    "<-> TML player links learned from linked matches, one-to-one, so each person has one canonical id; the "
    "unverified surname-and-initial guess removed; crosswalk conflicts listed and resolved to the TML identity; a "
    "build-stopping check for any remaining cross-source duplicate or split identity. provider_period gains a version "
    "argument; the frozen holdout and rehearse commands are pinned to version 1. No model, feature, parameter, "
    "training date, dataset, input file, or evaluation rule changed.")


def erratum():
    from matchup_dna.phase4_experiment import AMENDMENT_PATH, PROTOCOL_PATH, head_commit
    if ERRATUM_PATH.exists():
        raise SystemExit(f"{ERRATUM_PATH} already exists. It is never overwritten.")
    if not SUMMARY_PATH.exists():
        raise SystemExit("Run `evaluate` first; the erratum records its results.")
    protocol, amendment, commit, changed_hashes = check_correction_state()
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if summary["changed_files_sha256"] != changed_hashes:
        raise SystemExit("The code differs from the code the corrected evaluation ran on; rerun is not allowed, so stop.")
    diagnostics = json.loads((CORRECTION_DIR / "diagnostics.json").read_text(encoding="utf-8"))

    keys = ("rows", "dates", "gap", "se", "low", "high", "p", "month_se", "month_low", "month_high", "month_p")

    def gap_record(g):
        return {k: (round(g[k], 4) if isinstance(g[k], float) else g[k]) for k in keys}

    def brief(s):
        ra = s["round_aware"]
        return {"rows": s["rows"],
                "scores": {name: {k: round(v[k], 4) for k in ("log_loss", "brier", "accuracy")}
                           for name, v in s["scores"].items()},
                "calibration": {name: {k: round(v, 3) for k, v in c.items()} for name, c in s["calibration"].items()},
                "gap_P4_minus_P3": {t: gap_record(g) for t, g in s["gaps"].items()},
                "round_aware_R0_minus_reference": dict(
                    gap_record(ra), reference_log_loss=round(ra["reference"]["log_loss"], 4),
                    R0_log_loss=round(ra["R0"]["log_loss"], 4),
                    **{t: dict(gap_record(ra[t]), reference_log_loss=round(ra[t]["reference"]["log_loss"], 4),
                               R0_log_loss=round(ra[t]["R0"]["log_loss"], 4)) for t in ("ATP", "WTA")}),
                "ranking_benchmark": s["ranking"], "disagreements": s["disagreements"]}

    reconciliation = json.loads((CORRECTION_DIR / "reconciliation.json").read_text(encoding="utf-8"))
    checks = ("schedule_clashes", "repeated_rounds", "ids_with_unrelated_names", "full_names_with_several_ids",
              "sackmann_overlaps")

    contents = {
        "erratum": 1,
        "kind": "data-integrity correction after unblinding (not an amendment of the frozen procedure)",
        "applies_to": str(PROTOCOL_PATH.relative_to(ROOT)), "protocol_sha256": sha256(PROTOCOL_PATH),
        "amendment_1_sha256": sha256(AMENDMENT_PATH), "created": datetime.date.today().isoformat(),
        "status": "The corrected June-October 2026 evaluation is retrospective and post-unblinding, not a new independent "
                  "confirmation. The original run stays the result of the pre-registered procedure; it is not claimed "
                  "to have established significance, whatever the corrected interval shows.",
        "defect": ERRATUM_DEFECT, "fix": ERRATUM_FIX,
        "code_base_commit": head_commit(), "frozen_code_commit": commit,
        "changed_files_sha256": changed_hashes,
        "code_commit": "to be recorded by the user's commit; `python -m matchup_dna.phase4_correction check` confirms "
                       "the committed files equal these hashes",
        "tests": ["tests/test_heldout.py"],
        "diagnostics": {k: v for k, v in diagnostics.items() if k != "crosswalk_audit"},
        "independent_reconciliation": {
            version: {check: len(result[check]) for check in checks} for version, result in reconciliation.items()},
        "reconciliation_flags_in_version_2": {
            "items": reconciliation["version_2"]["schedule_clashes"],
            "explanation": "genuine TennisData.app additions inside a week TML also covers: TML lacks the London WTA "
                           "R32 Tatjana Maria d. Maria Sakkari and the Singapore WTA SF walkover Talia Gibson over "
                           "Tatiana Prozorova (unrated); not duplicates"},
        "limitations": [
            "post-unblinding: the defect was found, and the fix written, after every held-out outcome had been seen",
            "Sackmann files some Davis Cup matches under a second id for one person (Adolfo Daniel Vallejo under "
            "118808; Menelaos Efstathiou under 144949 and 213713). Phases 1-4 training data are frozen and unchanged",
            "the January-May 2026 rehearsal (outcome-free, before the freeze) also contained 41 such duplicates",
            "a genuine TennisData.app addition keeps its own tournament key, so round-aware values of that edition "
            "do not see it (2 rows; one unrated)",
            "the selected Phase 3 and Phase 4 models also differ in L2 (ATP 1000 vs 10, WTA 100 vs 0), so the gain "
            "is not attributable to serve-return features alone"],
        "crosswalk_entries_contradicted_by_match_evidence": diagnostics["crosswalk_audit"],
        "original_result_preserved": {"artifacts": ["results/phase4/final/heldout_predictions.csv",
                                                    "results/phase4/experiments/holdout.txt"],
                                      "published": PUBLISHED_ORIGINAL, "reproduced": brief(summary["original"])},
        "corrected_result": brief(summary["corrected"]),
        "removed_rows": summary["removed_rows"], "prediction_status": summary["prediction_status"],
        "change_reasons": summary["change_reasons"],
        "outputs": ["results/phase4/correction/", "results/phase4/corrected/"],
        "inputs_unchanged": True,
    }
    def core(s):  # fields every run recorded
        return ({n: {k: round(v[k], 6) for k in ("log_loss", "brier", "accuracy")} for n, v in s["scores"].items()},
                {t: (round(g["gap"], 6), round(g["se"], 6)) for t, g in s["gaps"].items()},
                (round(s["round_aware"]["gap"], 6), round(s["round_aware"]["se"], 6)), s["rows"])

    contents["earlier_corrected_runs"] = []
    for folder in sorted(RESULTS_DIR.joinpath("phase4").glob("corrected_*_run")):
        earlier = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        same_fix = all(earlier["changed_files_sha256"].get(path) == changed_hashes.get(path) for path in FIX_FILES)
        contents["earlier_corrected_runs"].append({
            "folder": str(folder.relative_to(ROOT)).replace("\\", "/"),
            "why": "evaluate records the hash of every changed file, so it was rerun after later edits to the post-hoc "
                   "scripts and to this record; the fix itself did not change",
            "fix_files_identical": same_fix, "corrected_results_identical": core(earlier["corrected"]) == core(summary["corrected"])})
        if not same_fix:
            raise SystemExit("The fix changed after an earlier corrected run; that must be disclosed, not recorded silently.")
    ERRATUM_PATH.write_text(json.dumps(contents, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(contents, indent=2, default=str))
    print(f"\nWritten to {ERRATUM_PATH}.")


def check():
    record = json.loads(ERRATUM_PATH.read_text(encoding="utf-8"))
    differ = [path for path, digest in record["changed_files_sha256"].items() if sha256(ROOT / path) != digest]
    if differ:
        raise SystemExit("These files differ from the erratum's hashes:\n" + "\n".join(differ))
    print(f"All {len(record['changed_files_sha256'])} changed files match {ERRATUM_PATH.name}.")


def main():
    parser = argparse.ArgumentParser(description="Phase 4 erratum 1")
    parser.add_argument("command", choices=["diagnose", "reconcile", "evaluate", "erratum", "check"])
    args = parser.parse_args()
    {"diagnose": diagnose, "reconcile": reconcile, "evaluate": evaluate, "erratum": erratum, "check": check}[args.command]()


if __name__ == "__main__":
    main()

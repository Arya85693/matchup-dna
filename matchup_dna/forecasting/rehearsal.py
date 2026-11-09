"""Rehearsal: the production path replayed on past days, compared with the research path on the same matches.

    python -m matchup_dna.forecasting rehearse --days 2026-07-01 2026-09-03 ...

For each day, the provider rows are cut as a snapshot taken at 00:00 UTC would have held them
(pipeline.replay_sources), the history and fixtures are assembled from that cut, and a forecast run is issued at
00:00 UTC into a store in "replay" mode. Results are then attached from the full snapshot and the replayed forecasts
are scored. Nothing here is a forecast record: every number is a rehearsal of past matches, and the June-October
2026 outcomes were already seen in Phase 4.

The comparison with the research path. Phase 4's corrected held-out rebuild built a feature row for every match
from the full period's data; the frozen artifacts reproduce its predictions exactly (frozen_models.verify). Each
replayed forecast is matched to that research row by tour, edition, round and the two canonical players. Three
reasons can make them differ, and the comparison separates them:

1. Rank source. A fixture carries the rank TennisData.app shows before the match. The research row carries the rank
   TML printed on the completed match. The comparison is repeated with the research row's ranks put into the replayed
   row ("rank-controlled"); then only the next two reasons remain.
2. Point in time. The replay sees only results dated before the day, so a player still finishing an earlier event
   (Phase 3's overlap case), or identity evidence that arrived later, can differ.
3. A defect in the production path. If the rank-controlled probabilities and the other inputs agree, the production
   path computes exactly what the research path computes.
"""
import datetime
import json
from collections import Counter, defaultdict

import numpy as np

from matchup_dna.elo import RESULTS_DIR
from matchup_dna.forecasting import pipeline
from matchup_dna.forecasting.frozen_models import ROUND_AWARE, TOURNAMENT_START, load_models
from matchup_dna.forecasting.history import assemble, load_sources
from matchup_dna.forecasting.records import UTC
from matchup_dna.forecasting.store import Store

OUTPUT_DIR = RESULTS_DIR / "phase6" / "rehearsal"
DEFAULT_DAYS = ("2026-06-10", "2026-07-01", "2026-07-08", "2026-08-05", "2026-08-13", "2026-09-03",
                "2026-09-09", "2026-10-08", "2026-10-22", "2026-10-29")
COMPARED_FIELDS = ("elo_diff", "surface_elo_diff", "a_days_since", "b_days_since", "a_form", "b_form",
                   "a_serve_adjusted", "b_serve_adjusted", "a_return_adjusted", "b_return_adjusted",
                   "a_ra_elo_shift", "b_ra_elo_shift", "a_ra_games_won_share", "b_ra_games_won_share")
EXACT = 1e-9


def research_rows():
    """Phase 4's corrected held-out rows (June-October 2026) with both frozen models' probabilities."""
    from matchup_dna.phase4_experiment import HELD_OUT, PROTOCOL_PATH, provider_period
    rows, _, _, _ = provider_period(*HELD_OUT, unseal_with=PROTOCOL_PATH, version=2)
    held = [r for r in rows if r["tourney_date"] >= HELD_OUT[0]]
    models = load_models()
    p = models[TOURNAMENT_START].predict(held)
    later = [i for i, r in enumerate(held) if r["ra_later_round"]]
    r0 = dict(zip(later, models[ROUND_AWARE].predict([held[i] for i in later])))
    for i, row in enumerate(held):
        row["p_ts"] = float(p[i])
        row["p_r0"] = float(r0[i]) if i in r0 else None
    return held


def oriented(row, field, low):
    """A row's value for the lower-id player (a_ fields) or as low-minus-high (differences)."""
    value = row[field]
    if value is None:
        return None
    if field.endswith("_diff"):
        return value if row["a_id"] == low else -value
    side = field[:2]
    if (row["a_id"] == low) == (side == "a_"):
        return value
    return row[("b_" if side == "a_" else "a_") + field[2:]]


def compare(store, research, models):
    """Pairs each replayed prediction with its research row and measures the differences."""
    index = defaultdict(list)
    for row in research:
        tourney_id = row["match_id"].split("|")[1]
        index[(row["tour"], tourney_id, row["round"], frozenset((row["a_id"], row["b_id"])))].append(row)
    report, details = Counter(), []
    gaps = {TOURNAMENT_START: [], ROUND_AWARE: []}
    controlled = {TOURNAMENT_START: [], ROUND_AWARE: []}
    field_equal = Counter()
    for prediction in store.predictions():
        content = json.loads(prediction["content_json"])
        row = content["inputs"]["row"]
        fixture = content["inputs"]["fixture"]
        kind = content["model_kind"]
        found = index.get((fixture["tour"], fixture["tourney_id"], fixture["round"], frozenset((row["a_id"], row["b_id"]))))
        if not found or len(found) != 1:
            report[f"{kind}: no single research row (edition or identity differs, or not rated)"] += 1
            continue
        research_row = found[0]
        low = min(row["a_id"], row["b_id"])
        p_low = prediction["p_a"] if row["a_id"] == low else 1 - prediction["p_a"]
        reference = research_row["p_ts"] if kind == TOURNAMENT_START else research_row["p_r0"]
        if reference is None:
            report[f"{kind}: research row has no R0 value (not in its later-round sample)"] += 1
            continue
        reference_low = reference if research_row["a_id"] == low else 1 - reference
        gaps[kind].append(abs(p_low - reference_low))
        swapped = dict(row)
        swapped["a_rank"] = research_row["a_rank"] if research_row["a_id"] == row["a_id"] else research_row["b_rank"]
        swapped["b_rank"] = research_row["b_rank"] if research_row["b_id"] == row["b_id"] else research_row["a_rank"]
        p_swapped = float(models[kind].predict([swapped])[0])
        p_swapped_low = p_swapped if row["a_id"] == low else 1 - p_swapped
        controlled[kind].append(abs(p_swapped_low - reference_low))
        report[f"{kind}: matched to a research row"] += 1
        if kind == TOURNAMENT_START:
            differing = []
            for field in COMPARED_FIELDS:
                mine, theirs = oriented(row, field, low), oriented(research_row, field, low)
                same = (mine is None and theirs is None) or (mine is not None and theirs is not None and
                                                             abs(mine - theirs) < EXACT)
                field_equal[(field, same)] += 1
                if not same and not field.startswith(("a_ra", "b_ra")):
                    differing.append(field)
            details.append({"match": f"{fixture['tourney_name']} {fixture['round']} {row['a_name']} v {row['b_name']}",
                            "gap": abs(p_low - reference_low), "rank_controlled_gap": abs(p_swapped_low - reference_low),
                            "differing_inputs": differing})
    return report, gaps, controlled, field_equal, details


def summary_lines(gaps, controlled, report, field_equal):
    lines = []
    for kind in (TOURNAMENT_START, ROUND_AWARE):
        for label, values in (("as issued", gaps[kind]), ("rank-controlled", controlled[kind])):
            if not values:
                continue
            v = np.array(values)
            lines.append(f"   {kind:<17} {label:<16} n {len(v):>4}  identical (<1e-9) {np.mean(v < EXACT):6.1%}  "
                         f"mean |diff| {v.mean():.5f}  median {np.median(v):.5f}  90th pct {np.quantile(v, 0.9):.5f}  "
                         f"max {v.max():.4f}  over 0.01: {int((v > 0.01).sum())}")
    for key, value in sorted(report.items()):
        lines.append(f"   {key}: {value}")
    for field in COMPARED_FIELDS:
        same, total = field_equal[(field, True)], field_equal[(field, True)] + field_equal[(field, False)]
        if total:
            lines.append(f"   input {field:<24} identical in {same / total:6.1%} of {total} matched rows")
    return lines


def rehearse(days, store_path=None):
    from matchup_dna.forecasting.prospective import score_store
    from matchup_dna.phase4_experiment import PROTOCOL_PATH
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    store_path = store_path or OUTPUT_DIR / f"replay_{stamp}.sqlite"
    store = Store(store_path, mode="replay")
    sources = load_sources(PROTOCOL_PATH)
    models = load_models()
    lines = [f"REHEARSAL (replay mode; not a forecast record). Store {store_path}", ""]
    for text in days:
        day = datetime.date.fromisoformat(text)
        tml_rows, td_rows = pipeline.replay_sources(sources, day)
        assembly = assemble(sources, tml_rows=tml_rows, td_rows=td_rows)
        as_of = datetime.datetime.combine(day, datetime.time(0, 0), UTC)
        run, counts = pipeline.forecast(store, sources, as_of, models=models, assembly=assembly, td_rows=td_rows)
        shown = {k: v for k, v in counts.items() if not k.startswith(("assembly", "provider records"))}
        lines.append(f"{text}: {run} {json.dumps(shown, sort_keys=True)}")
        print(lines[-1], flush=True)
    full = assemble(sources)
    run, counts = pipeline.settle(store, sources, datetime.datetime.now(UTC), assembly=full)
    lines.append(f"\nSettled from the full snapshot: {json.dumps(counts, sort_keys=True)}")
    problems = store.verify()
    lines.append(f"Chain and content hashes: {'intact' if not problems else problems[:5]}")

    research = research_rows()
    report, gaps, controlled, field_equal, details = compare(store, research, models)
    lines.append("\nPRODUCTION PATH AGAINST RESEARCH PATH (probability for the lower-id player)")
    lines += summary_lines(gaps, controlled, report, field_equal)
    worst = sorted(details, key=lambda d: -d["rank_controlled_gap"])[:15]
    lines.append("\nLargest rank-controlled differences (Model A), with the inputs that differ:")
    for d in worst:
        lines.append(f"   {d['rank_controlled_gap']:.4f} (as issued {d['gap']:.4f})  {d['match']}  "
                     f"{d['differing_inputs']}")
    lines.append("\nREPLAYED FORECASTS SCORED (descriptive; outcomes seen in Phase 4)")
    lines += score_store(store)
    output = OUTPUT_DIR / f"rehearsal_{stamp}.txt"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[len(days) + 2:]))
    print(f"\nWritten to {output}")
    return output

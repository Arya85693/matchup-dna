"""Data-quality audit of the Valuebetennis odds files, and the join to the model's matches (Phase 5).

    python -m matchup_dna.audit_valuebetennis

Writes results/phase5/audit/valuebetennis_audit.txt and .json, a manifest, the player crosswalk
(results/phase5/vb_crosswalk.csv) and the match links (results/phase5/links.csv; no model probability in it).
Everything under results/ is gitignored.

Outcome discipline: January 2024 onward is Phase 5's evaluation window, where no model-against-market comparison
may be made before the Phase 5 protocol is frozen. This audit computes no accuracy, log loss or return for the
market or the model in any period. Results are used only as a data check: whether the two sources name the same
winner for a linked match.
"""
import csv
import json
import statistics
from collections import Counter, defaultdict

from matchup_dna import market
from matchup_dna import market_link as ml
from matchup_dna import valuebetennis as vb
from matchup_dna.experiment import Output, manifest
from matchup_dna.phase5_dataset import PERIODS, PHASE5_DIR, PREDICTIONS, model_matches

AUDIT_DIR = PHASE5_DIR / "audit"
CATEGORY_ORDER = ("Grand Chelem", "Masters", "Main tour", "Coupe Davis / BJK Cup", "Challenger", "ITF", "")


def share(part, whole):
    return f"{part / whole:.1%}" if whole else "-"


def quantiles(values, points=(0.01, 0.25, 0.5, 0.75, 0.99)):
    if not values:
        return {}
    ordered = sorted(values)
    return {p: ordered[min(int(p * len(ordered)), len(ordered) - 1)] for p in points}


def section_files(out, rows, paths):
    out("1. FILES")
    found = []
    for path in paths:
        count = sum(1 for r in rows if r["source"] == path.name)
        days = [r["day"] for r in rows if r["source"] == path.name]
        digest = vb.sha256(path)
        found.append({"file": path.name, "rows": count, "sha256": digest})
        out(f"   {path.name}: {count:,} rows, {min(days)} to {max(days)}, sha256 {digest[:16]}")
    out(f"   Total {len(rows):,} rows; {len({r['vb_id'] for r in rows}):,} distinct match ids; first match "
        f"{min(r['start'] for r in rows):%Y-%m-%d %H:%M} UTC, last {max(r['start'] for r in rows):%Y-%m-%d %H:%M} UTC")
    out("   License: CC BY 4.0 (attribution required, commercial use allowed). The files stay private and gitignored.")
    return found


def section_population(out, rows):
    out("\n2. ROWS BY CATEGORY AND YEAR (category as Valuebetennis files it)")
    years = sorted({r["day"].year for r in rows})
    out("   " + f"{'category':<24}" + "".join(f"{y:>9}" for y in years) + f"{'total':>10}")
    for category in CATEGORY_ORDER:
        counts = Counter(r["day"].year for r in rows if r["category"] == category)
        out("   " + f"{category or '(blank)':<24}" + "".join(f"{counts[y]:>9,}" for y in years) + f"{sum(counts.values()):>10,}")
    out(f"   Men {sum(r['tour'] == 'ATP' for r in rows):,}; women {sum(r['tour'] == 'WTA' for r in rows):,}; "
        f"surface {dict(Counter((r['surface'], r['indoor']) for r in rows))}")


def section_integrity(out, rows):
    out("\n3. INTEGRITY")
    tour = [r for r in rows if r["level"] in vb.TOUR_LEVELS]
    names, ids = defaultdict(set), defaultdict(set)
    for r in rows:
        for name, i in zip(r["names"], r["ids"]):
            names[(r["tour"], i)].add(name)
            ids[(r["tour"], name)].add(i)
    pairs = Counter((r["tour"], frozenset(r["ids"]), r["day"]) for r in tour)
    found = {
        "duplicate match ids": len(rows) - len({r["vb_id"] for r in rows}),
        "winner id is neither player": sum(r["winner"] is None for r in rows),
        "a player against himself": sum(r["ids"][0] == r["ids"][1] for r in rows),
        "player ids with more than one name": sum(len(v) > 1 for v in names.values()),
        "names with more than one player id": sum(len(v) > 1 for v in ids.values()),
        "tour-level: same pair twice on one day": sum(v > 1 for v in pairs.values()),
        "tour-level: start time exactly 00:00:00 (no real time)": sum(r["midnight"] for r in tour),
        "tour-level: score blank": sum(r["score"] == "" for r in tour),
        "duration blank": sum(r["duration"] is None for r in rows),
        "names written as a pair 'A/B'": sum(any("/" in n for n in r["names"]) for r in rows),
        "tour-level qualifying rows (round codes 1-3)": sum(vb.is_qualifying(r) for r in rows),
    }
    for key, value in found.items():
        out(f"   {key}: {value:,}")
    out("   Doubles teams can also appear as two 'players' (Makoto Ninomiya v Ena Shibahara, Abu Dhabi 2021); they are")
    out("   not detectable from the text and fall out at the join, where no such singles match exists.")
    out("   Same pair twice on one day: mostly placeholder rows timed 00:00:00 next to the real row (Davis Cup Finals,")
    out("   ATP Cup); the join keeps at most one row per real match.")
    return found


def price_stats(rows, which):
    usable = [r for r in rows if vb.has_prices(r, which)]
    overrounds = [market.overround(r[which]) for r in usable]
    return usable, overrounds


def section_prices(out, rows):
    out("\n4. PRICES (usable = both decimal prices present and above 1.00)")
    out(f"   {'category':<24} {'rows':>8} {'opening usable':>15} {'closing usable':>15} {'median overround open':>22} "
        f"{'close':>7}")
    found = {}
    for category in CATEGORY_ORDER:
        subset = [r for r in rows if r["category"] == category]
        if not subset:
            continue
        opened, open_over = price_stats(subset, "open")
        closed, close_over = price_stats(subset, "close")
        found[category or "(blank)"] = {"rows": len(subset), "open": len(opened), "close": len(closed),
                                        "open_overround_median": statistics.median(open_over) if open_over else None,
                                        "close_overround_median": statistics.median(close_over) if close_over else None}
        out(f"   {category or '(blank)':<24} {len(subset):>8,} {share(len(opened), len(subset)):>15} "
            f"{share(len(closed), len(subset)):>15} {statistics.median(open_over) if open_over else 0:>22.4f} "
            f"{statistics.median(close_over) if close_over else 0:>7.4f}")
    tour = [r for r in rows if r["level"] in ("G", "M", "A")]
    out("\n   Grand Slam, Masters and main tour, by year")
    out(f"   {'year':<6} {'rows':>7} {'opening usable':>15} {'closing usable':>15} {'overround open p1/p25/p50/p75/p99':>40}")
    for year in sorted({r["day"].year for r in tour}):
        subset = [r for r in tour if r["day"].year == year]
        opened, over = price_stats(subset, "open")
        closed, _ = price_stats(subset, "close")
        q = quantiles(over)
        out(f"   {year:<6} {len(subset):>7,} {share(len(opened), len(subset)):>15} {share(len(closed), len(subset)):>15} "
            f"{'/'.join(f'{q[p]:.3f}' for p in sorted(q)):>40}")
    opened, open_over = price_stats(tour, "open")
    closed, close_over = price_stats(tour, "close")
    out(f"   Opening overround below 1.00 (both sides could be backed at a profit; stale or erroneous): "
        f"{sum(o < 1 for o in open_over):,}; above 1.15: {sum(o > 1.15 for o in open_over):,}")
    out(f"   Closing overround below 1.00: {sum(o < 1 for o in close_over):,}; above 1.15: {sum(o > 1.15 for o in close_over):,}")
    both = [r for r in tour if vb.has_prices(r, "open") and vb.has_prices(r, "close")]
    moves = [abs(market.multiplicative(r["close"])[0] - market.multiplicative(r["open"])[0]) for r in both]
    q = quantiles(moves, (0.5, 0.9, 0.99))
    out(f"   Opening to closing move in player 1's margin-free probability (no outcome used), {len(both):,} matches: "
        f"median {q[0.5]:.3f}, 90th percentile {q[0.9]:.3f}, 99th {q[0.99]:.3f}")
    out("   Neither price has its own timestamp. The opening price is treated as the earliest recorded and the only one a")
    out("   decision before the match may use; the closing price is a benchmark only.")
    return found


def section_margin(out, rows):
    out("\n5. MARGIN REMOVAL: how much the method matters (no outcome used)")
    tour = [r for r in rows if r["level"] in ("G", "M", "A") and vb.has_prices(r, "open")]
    favourites = defaultdict(list)
    for r in tour:
        first = 0 if r["open"][0] <= r["open"][1] else 1
        for method in market.METHODS:
            favourites[method].append(market.fair(r["open"], method)[first])
    base = favourites["multiplicative"]
    out(f"   {len(tour):,} tour-level matches with opening prices; favourite's margin-free probability")
    found = {}
    for method in market.METHODS:
        values = favourites[method]
        gap = [v - b for v, b in zip(values, base)]
        found[method] = {"median": statistics.median(values), "mean_minus_multiplicative": statistics.fmean(gap)}
        out(f"   {method:<15} median {statistics.median(values):.4f}; mean minus multiplicative {statistics.fmean(gap):+.4f}; "
            f"largest {max(gap, key=abs):+.4f}")
    out("   The methods differ by up to a few probability points on long prices. Which one to use is chosen on the")
    out("   2021-2023 development matches only, before any evaluation (Phase 5 protocol).")
    return found


def unlinked_reasons(model_rows, links, vb_rows):
    """Why each unlinked model match has no odds row: a row with both names exists elsewhere in time, one player's
    name appears that week with a different opponent spelling, or nothing at all."""
    linked = {m["match_id"] for _, m, _ in links}
    by_names = defaultdict(list)
    by_player = defaultdict(list)
    for r in vb_rows:
        by_names[(r["tour"], frozenset(ml.name_key(n) for n in r["names"]))].append(r)
        for n in r["names"]:
            by_player[(r["tour"], ml.name_key(n))].append(r)
    reasons = Counter()
    for m in model_rows:
        if m["match_id"] in linked:
            continue
        both = by_names.get((m["tour"], frozenset((ml.name_key(m["a_name"]), ml.name_key(m["b_name"])))), ())
        near = [r for r in both if ml.in_window(r, m)]
        if near:
            reasons["a row with both names is in the window (left out: ambiguous, round, or winner check)"] += 1
        elif both:
            reasons["a row with both names exists, outside the date window"] += 1
        elif any(ml.in_window(r, m) for n in (m["a_name"], m["b_name"]) for r in by_player.get((m["tour"], ml.name_key(n)), ())):
            reasons["one player's name appears that week; the other is spelled differently or absent"] += 1
        else:
            reasons["no row for either name that week (event or player missing from Valuebetennis)"] += 1
    return reasons


def section_join(out, model_rows, result, vb_rows):
    out("\n6. JOIN TO THE MODEL'S MATCHES (names and the window first; then verified player ids; see market_link)")
    for key, value in result["report"].items():
        out(f"   {key}: {value:,}")
    links = result["links"]
    linked = {m["match_id"]: r for r, m, _ in links}
    out(f"\n   Model matches linked to an odds row, with usable opening and closing prices")
    out(f"   {'period':<30} {'tour':<5} {'model matches':>13} {'linked':>14} {'opening usable':>15} {'closing usable':>15}")
    coverage = {}
    for period in PERIODS:
        for tour in ("ATP", "WTA", "Both"):
            subset = [m for m in model_rows if m["period"] == period and (tour == "Both" or m["tour"] == tour)]
            rows = [linked[m["match_id"]] for m in subset if m["match_id"] in linked]
            opened = sum(vb.has_prices(r, "open") for r in rows)
            closed = sum(vb.has_prices(r, "close") for r in rows)
            coverage[f"{period} {tour}"] = {"model": len(subset), "linked": len(rows), "open": opened, "close": closed}
            out(f"   {period:<30} {tour:<5} {len(subset):>13,} {len(rows):>7,} {share(len(rows), len(subset)):>6} "
                f"{opened:>8,} {share(opened, len(subset)):>6} {closed:>8,} {share(closed, len(subset)):>6}")
    out("\n   By Sackmann level (all periods)")
    for level in sorted({m["tourney_level"] for m in model_rows}):
        subset = [m for m in model_rows if m["tourney_level"] == level]
        rows = [linked[m["match_id"]] for m in subset if m["match_id"] in linked]
        out(f"   {level:<6} {len(subset):>6,} model matches; linked {share(len(rows), len(subset)):>6}; opening usable "
            f"{share(sum(vb.has_prices(r, 'open') for r in rows), len(subset)):>6}")
    reasons = unlinked_reasons(model_rows, links, vb_rows)
    out("\n   Why model matches are not linked")
    for reason, count in reasons.most_common():
        out(f"   {count:>6,}  {reason}")
    names = {}
    for m in model_rows:
        names[(m["tour"], m["a_id"])], names[(m["tour"], m["b_id"])] = m["a_name"], m["b_name"]
    vb_names = {(r["tour"], i): n for r in vb_rows for n, i in zip(r["names"], r["ids"])}
    out(f"\n   Name variants mapped from opponent evidence ({len(result['variants'])}; check each by eye):")
    for (tour, vb_id), model_ids in sorted(result["variants"].items(), key=lambda item: vb_names[item[0]]):
        shown = " / ".join(f"{names.get((tour, i))!r} ({i})" for i in sorted(model_ids))
        out(f"      {tour} {vb_names[(tour, vb_id)]!r} (Valuebetennis {vb_id}) = {shown}")
    out(f"   Players the model holds under several ids with one identical name, mapped to all ({len(result['several_ids'])}):")
    for (tour, vb_id), model_ids in sorted(result["several_ids"].items()):
        out(f"      {tour} {vb_names[(tour, vb_id)]!r} (Valuebetennis {vb_id}) = model ids {sorted(model_ids)}")
    out(f"   Name-variant candidates rejected ({len(result['variants_rejected'])}):")
    for item in result["variants_rejected"]:
        votes = {names.get((item["tour"], k), k): v for k, v in item["votes"].items()}
        out(f"      {item['tour']} {vb_names[(item['tour'], item['vb_id'])]!r}: {item['reason']}; votes {votes}")
    out(f"\n   Player conflicts (a Valuebetennis id observed with two model ids; not used): {result['conflicts']}")
    out(f"   Linked pairs whose sources name different winners (left out): {len(result['winner_mismatches'])}")
    for item in result["winner_mismatches"]:
        out(f"      {item}")
    out(f"   Left out for review (never merged): {dict(Counter(x['reason'] for x in result['review']))}")
    gaps = Counter((r["day"] - ml.to_day(m["tourney_date"])).days for r, m, _ in links)
    out(f"   Odds row day minus model tourney_date, days: {dict(sorted(gaps.items()))}")
    before = sum((r["day"] - ml.to_day(m["tourney_date"])).days < 0 for r, m, _ in links)
    out(f"   Linked matches played before the model's tourney_date: {before:,} (Sackmann dates some events from the")
    out("   Monday and the first matches are on the Sunday; the model's features use only earlier tournament dates, so a")
    out("   tournament-start probability exists before every one of these matches).")
    return coverage, reasons


def write_outputs(result):
    PHASE5_DIR.mkdir(parents=True, exist_ok=True)
    with open(PHASE5_DIR / "vb_crosswalk.csv", "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["tour", "valuebetennis_id", "model_id"])
        for (tour, vb_id), model_ids in sorted(result["crosswalk"].items(), key=lambda item: (item[0][0], int(item[0][1]))):
            writer.writerow([tour, vb_id, " ".join(str(i) for i in sorted(model_ids))])
    with open(PHASE5_DIR / "links.csv", "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["match_id", "vb_id", "vb_player1_is_a", "start_utc", "category", "edition",
                         "open1", "open2", "close1", "close2"])
        for r, m, same in sorted(result["links"], key=lambda item: item[1]["match_id"]):
            writer.writerow([m["match_id"], r["vb_id"], int(same), r["start"].strftime("%Y-%m-%d %H:%M:%S"),
                             r["category"], r["edition"], *(("" if x is None else x) for x in r["open"] + r["close"])])


def main():
    out = Output()
    out("VALUEBETENNIS AUDIT (Phase 5). No accuracy, log loss or return is computed for the market or the model; results")
    out("are used only to check that linked rows name the same winner in both sources.\n")
    paths = vb.files()
    rows = vb.load_valuebetennis()
    files_found = section_files(out, rows, paths)
    section_population(out, rows)
    integrity = section_integrity(out, rows)
    prices = section_prices(out, rows)
    margins = section_margin(out, rows)
    models = model_matches()
    result = ml.link(rows, models)
    coverage, reasons = section_join(out, models, result, rows)
    write_outputs(result)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / "valuebetennis_audit.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    summary = {"files": files_found, "integrity": integrity, "prices": prices, "margin_methods": margins,
               "join": dict(result["report"]), "coverage": coverage, "unlinked_reasons": dict(reasons),
               "conflicts": result["conflicts"], "winner_mismatches": result["winner_mismatches"],
               "variants": {f"{k[0]}|{k[1]}": sorted(v) for k, v in result["variants"].items()},
               "several_ids": {f"{k[0]}|{k[1]}": sorted(v) for k, v in result["several_ids"].items()},
               "variants_rejected": result["variants_rejected"],
               "review": result["review"]}
    (AUDIT_DIR / "valuebetennis_audit.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (AUDIT_DIR / "valuebetennis_audit_manifest.json").write_text(
        json.dumps(manifest("valuebetennis audit", paths + [PREDICTIONS]), indent=2), encoding="utf-8")
    print(f"\nWritten to {AUDIT_DIR}")


if __name__ == "__main__":
    main()

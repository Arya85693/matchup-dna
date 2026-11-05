"""Focused audit: can physical-workload, recovery, and route-difficulty features be calculated correctly?

    python -m matchup_dna.audit_workload

Coverage and structure only. Nothing here relates a feature to who won, so the audit cannot steer which
features are pre-registered. Sackmann years 2010 to the week of 25 May 2026 are read in full. TennisIsMyLife
and TennisData.app are read through their sealed readers: for the held-out period only round labels and
availability flags are counted, in aggregate. Writes results/phase4/audit/workload_audit.txt and a manifest.
"""
import json
import statistics
from collections import Counter, defaultdict

from matchup_dna import tennisdata as td
from matchup_dna import tennisismylife as tml
from matchup_dna.audit_tennisdata import AUDIT_DIR, link_population, sackmann_overlap, share
from matchup_dna.audit_tennisismylife import SNAPSHOT, to_sackmann
from matchup_dna.crosswalk import load_player_names
from matchup_dna.elo import ELO_K, SURFACE_ELO_K, is_rated, run_elo
from matchup_dna.experiment import Output, manifest
from matchup_dna.load import TOURS, match_files
from matchup_dna.round_aware import KNOCKOUT, round_aware_features, round_order
from matchup_dna.workload import load_matches_with_workload, match_workload, parse_sets, recent_workload

PERIODS = (("2010-15", 20100101, 20160101), ("2016-20", 20160101, 20210101), ("2021-23", 20210101, 20240101),
           ("2024-May 26", 20240101, 20260601))
LEVEL_GROUPS = {"G": "Grand Slam", "M": "Masters/1000", "PM": "Masters/1000", "T1": "Masters/1000",
                "P": "500 (WTA)", "T2": "500 (WTA)", "A": "250-500 (ATP)", "I": "250 (WTA)", "T3": "250 (WTA)",
                "T4": "250 (WTA)", "T5": "250 (WTA)", "F": "Tour Finals", "D": "Davis/BJK Cup", "O": "Olympics"}


def period_of(date):
    for name, start, end in PERIODS:
        if start <= date < end:
            return name
    return None


def level_group(level):
    return LEVEL_GROUPS.get(level, f"other ({level})")


def percentiles(values, points=(0.1, 1, 5, 50, 95, 99, 99.9)):
    ordered = sorted(values)
    return {p: ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))] for p in points}


def pearson(xs, ys):
    return statistics.correlation(xs, ys) if len(xs) > 2 else float("nan")


def section_inputs(out, matches):
    out("1. WORKLOAD INPUTS IN SACKMANN, BY TOUR, PERIOD, AND TOURNAMENT CATEGORY")
    out("   Share of matches played on court (completed, retired, defaulted with games) with each measure usable.")
    table = defaultdict(Counter)
    for match in matches:
        period = period_of(match["tourney_date"])
        if period is None:
            continue
        load = match_workload(match)
        key = (match["tour"], period, level_group(match["tourney_level"]))
        table[key]["rows"] += 1
        table[key][load["kind"]] += 1
        if load["kind"] in ("played", "partial"):
            table[key]["on court"] += 1
            for measure in ("games", "points", "minutes"):
                table[key][measure] += load[measure] is not None
            for flag in load["flags"]:
                table[key][flag] += 1
    for tour in TOURS:
        for period, _, _ in PERIODS:
            keys = sorted(k for k in table if k[:2] == (tour, period))
            total = sum((table[k] for k in keys), Counter())
            out(f"   {tour} {period:<12} rows {total['rows']:>6,}  completed {total['played']:>6,}  retired/def "
                f"{total['partial']:>4,}  walkover {total['walkover']:>4,}  unknown {total['unknown']:>3,}  |  games "
                f"{total['games'] / total['on court']:.1%}  points {total['points'] / total['on court']:.1%}  minutes "
                f"{total['minutes'] / total['on court']:.1%}")
            for key in keys:
                row = table[key]
                if row["on court"]:
                    out(f"      {key[2]:<16} {row['on court']:>6,} on court: games {row['games'] / row['on court']:6.1%}"
                        f"  points {row['points'] / row['on court']:6.1%}  minutes {row['minutes'] / row['on court']:6.1%}"
                        f"  implausible points {row['implausible points']}, minutes {row['implausible minutes']}")
    return table


def section_plausibility(out, matches):
    out("\n2. PLAUSIBILITY (completed matches, 2010-2020, before any rule is applied)")
    for tour in TOURS:
        minutes_per_game, points_per_game, unparsed = [], [], Counter()
        for match in matches:
            if match["tour"] != tour or not 20100101 <= match["tourney_date"] < 20210101:
                continue
            if match["outcome"] != "completed":
                continue
            sets = parse_sets(match["score"])
            if not sets:
                unparsed[match["score"][:20]] += 1
                continue
            games = sum(a + b if kind == "set" else 1 for a, b, kind in sets)
            if match["minutes"] is not None and match["minutes"] > 0:
                minutes_per_game.append(match["minutes"] / games)
            if match["w_svpt"] and match["l_svpt"]:
                points_per_game.append((match["w_svpt"] + match["l_svpt"]) / games)
        out(f"   {tour} minutes per game, percentiles: {({k: round(v, 2) for k, v in percentiles(minutes_per_game).items()})}"
            f"; below 1.5: {sum(v < 1.5 for v in minutes_per_game)}, above 15: {sum(v > 15 for v in minutes_per_game)}")
        out(f"   {tour} points per game, percentiles: {({k: round(v, 2) for k, v in percentiles(points_per_game).items()})}"
            f"; below 4 (impossible): {sum(v < 4 for v in points_per_game)}, above 20: {sum(v > 20 for v in points_per_game)}")
        out(f"   {tour} completed matches whose score could not be read: {sum(unparsed.values())} {dict(unparsed.most_common(5))}")


def section_correlation(out, matches):
    out("\n3. HOW THE THREE MEASURES RELATE (completed matches 2016-2020 with all three usable; no outcomes involved)")
    for tour in TOURS:
        for best_of in (3, 5):
            games, points, minutes = [], [], []
            for match in matches:
                if match["tour"] != tour or match["best_of"] != best_of or not 20160101 <= match["tourney_date"] < 20210101:
                    continue
                load = match_workload(match)
                if load["kind"] == "played" and None not in (load["games"], load["points"], load["minutes"]):
                    games.append(load["games"]); points.append(load["points"]); minutes.append(load["minutes"])
            if len(games) > 100:
                out(f"   {tour} best of {best_of}: {len(games):,} matches; correlation games-points {pearson(games, points):.3f}, "
                    f"games-minutes {pearson(games, minutes):.3f}, points-minutes {pearson(points, minutes):.3f}; "
                    f"median games {statistics.median(games)}, points {statistics.median(points)}, minutes {statistics.median(minutes)}")


def section_structure(out, matches):
    out("\n4. ROUND STRUCTURE OF EDITIONS (Sackmann, 2010 to May 2026)")
    editions = defaultdict(list)
    for match in matches:
        if match["tourney_date"] >= 20100101 and match["winner_id"] != match["loser_id"]:
            editions[(match["tour"], match["tourney_id"])].append(match)
    labels = Counter((m["tour"], level_group(m["tourney_level"]), m["round"]) for ms in editions.values() for m in ms
                     if round_order(m["round"]) is None)
    out(f"   Round labels outside R128-F and RR, by tour and category: {dict(labels.most_common())}")
    kinds = Counter()
    for (tour, _), members in editions.items():
        rounds = {m["round"] for m in members}
        if members[0]["tourney_level"] == "D":
            kind = "team tie (level D)"
        elif any(round_order(r) is None for r in rounds):
            kind = "has an unordered round"
        elif "RR" in rounds:
            kind = "round robin + knockout" if rounds - {"RR"} else "round robin only"
        else:
            kind = "knockout"
        kinds[(tour, kind)] += 1
    out(f"   Editions by structure: {dict(sorted(kinds.items()))}")
    draws = Counter((m[0]["tour"], m[0]["draw_size"]) for m in editions.values() if m[0]["tourney_level"] != "D")
    out(f"   Draw sizes (non-team editions): {dict(sorted(draws.items(), key=lambda kv: (kv[0][0], -kv[1]))[:30])}")


def section_eligibility(out, matches, found):
    out("\n5. ROUND-AWARE ELIGIBILITY OF RATED MATCHES (both players' earlier rounds established)")
    rated = [m for m in matches if is_rated(m) and period_of(m["tourney_date"])]
    table = defaultdict(Counter)
    for match in rated:
        entry = found[match["key"]]
        table[(match["tour"], period_of(match["tourney_date"]))]["rated"] += 1
        table[(match["tour"], period_of(match["tourney_date"]))]["eligible" if entry["eligible"] else entry["reason"]] += 1
    for key in sorted(table):
        row = table[key]
        reasons = {k: v for k, v in row.items() if k not in ("rated", "eligible")}
        out(f"   {key[0]} {key[1]:<12} rated {row['rated']:>6,}  eligible {share(row['eligible'], row['rated'])}  not: {reasons}")
    by_round = defaultdict(Counter)
    for match in rated:
        if match["tourney_date"] < 20240101:
            by_round[(match["tour"], match["round"])][found[match["key"]]["eligible"]] += 1
    out("   2010-2023 by round (eligible / rated):")
    for tour in TOURS:
        out("      " + tour + "  " + "  ".join(
            f"{r} {share(by_round[(tour, r)][True], sum(by_round[(tour, r)].values()))}"
            for r in list(KNOCKOUT) + ["RR"] if sum(by_round[(tour, r)].values())))


def section_availability(out, matches, found):
    out("\n6. WORKLOAD AND ROUTE VALUES ON ELIGIBLE MATCHES WHERE BOTH PLAYERS HAVE AT LEAST ONE EARLIER MATCH")
    table = defaultdict(Counter)
    for match in matches:
        entry = found.get(match["key"])
        period = period_of(match["tourney_date"])
        if not entry or not entry["eligible"] or period is None:
            continue
        sides = (entry["winner"], entry["loser"])
        row = table[(match["tour"], period)]
        row["eligible"] += 1
        row["later round"] += max(s["matches"] + s["walkovers"] for s in sides) > 0
        if min(s["matches"] + s["walkovers"] for s in sides) == 0:
            continue
        row["with history"] += 1
        for measure in ("games", "points", "minutes"):
            row[measure] += all(s[measure] is not None for s in sides)
        row["route"] += all(s["route_relative_elo"] is not None for s in sides)
        row["walkover earlier"] += any(s["walkovers"] for s in sides)
        row["retirement earlier"] += any(s["partial"] for s in sides)
        row["qualifier or lucky loser"] += any(s["entry"] in ("Q", "LL") for s in sides)
        row["faced"] += sum(s["faced"] for s in sides)
        row["unreliable faced"] += sum(s["unreliable_faced"] for s in sides)
    for key in sorted(table):
        row = table[key]
        n = row["with history"]
        out(f"   {key[0]} {key[1]:<12} eligible {row['eligible']:>6,}, after the first round {row['later round']:>6,}, "
            f"both with history {n:>6,}: games known "
            f"{row['games'] / n:6.1%}, points {row['points'] / n:6.1%}, minutes {row['minutes'] / n:6.1%}, route "
            f"{row['route'] / n:6.1%}; a walkover earlier {row['walkover earlier'] / n:.1%}, a retirement earlier "
            f"{row['retirement earlier'] / n:.1%}, a qualifier or lucky loser {row['qualifier or lucky loser'] / n:.1%};"
            f" opponents faced with under 20 rated matches {row['unreliable faced'] / max(row['faced'], 1):.1%}")


def section_recent(out, matches):
    out("\n7. TOURNAMENT-START WORKLOAD: PREVIOUS 14 DAYS (strictly earlier tournament dates)")
    targets = [m for m in matches if is_rated(m) and period_of(m["tourney_date"])]
    found = recent_workload(matches, targets)
    table = defaultdict(Counter)
    for match in targets:
        row = table[(match["tour"], period_of(match["tourney_date"]))]
        for side in ("winner", "loser"):
            values = found[(match["key"], side)]
            row["sides"] += 1
            row["some"] += values["matches"] > 0
            for measure in ("games", "points", "minutes"):
                row[measure] += values[measure] is not None
    for key in sorted(table):
        row = table[key]
        out(f"   {key[0]} {key[1]:<12} player-matches {row['sides']:>7,}: some match in the window {row['some'] / row['sides']:6.1%};"
            f" sum known: games {row['games'] / row['sides']:6.1%}, points {row['points'] / row['sides']:6.1%}, "
            f"minutes {row['minutes'] / row['sides']:6.1%}")


def section_sources(out):
    out("\n8. 2025 TO MAY 2026: WHAT TML AND TENNISDATA.APP ADD (open rows only)")
    sackmann, names = sackmann_overlap(), load_player_names()
    tml_rows = tml.load_tml()
    open_tml = [r for r in tml_rows if not r["sealed"]]
    linked = [r for r in to_sackmann(open_tml, sackmann, names) if r["status"] == "linked" and r["same_order"]]
    minutes = Counter()
    gaps = []
    for result in linked:
        mine, theirs = result["item"]["minutes"].strip(), result["target"]["raw"]["minutes"].strip()
        minutes["both" if mine and theirs else "TML only" if mine else "Sackmann only" if theirs else "neither"] += 1
        if mine and theirs:
            gaps.append(abs(int(mine) - int(theirs)))
    out(f"   Minutes on linked matches: {dict(minutes)}; where both: identical {share(sum(g == 0 for g in gaps), len(gaps))},"
        f" within 5 minutes {share(sum(g <= 5 for g in gaps), len(gaps))}")
    points = Counter()
    for result in linked:
        raw, row = result["target"]["raw"], result["item"]
        have_s = raw["w_svpt"].strip() and raw["l_svpt"].strip()
        have_t = row["w_svpt"].strip() and row["l_svpt"].strip()
        points["both" if have_s and have_t else "TML only" if have_t else "Sackmann only" if have_s else "neither"] += 1
    out(f"   Total points (both serve-point counts) on linked matches: {dict(points)}")

    order_check = Counter()
    by_edition = defaultdict(lambda: defaultdict(set))
    for row in open_tml:
        if row["source_file"].startswith("2026") and round_order(row["round"]):
            by_edition[(row["tour"], row["tourney_id"])][round_order(row["round"])].add(int(row["tourney_date"]))
    for rounds in by_edition.values():
        ordered = [min(rounds[k]) for k in sorted(rounds)]
        order_check["dates never decrease with round" if ordered == sorted(ordered) else "a later round dated earlier"] += 1
        order_check["one date per round" if all(len(v) == 1 for v in rounds.values()) else "a round with several dates"] += 1
    out(f"   TML 2026 knockout editions (open): {dict(order_check)}")

    td_rows = td.load_provider()
    td_open = [r for r in td_rows if not r["sealed"] and td.is_main_draw(r)]
    td_linked, _, td_by_ids = link_population(td_open, sackmann, names)
    games = Counter()
    for result in [r for r in td_linked if r["status"] == "linked"] + td_by_ids:
        row, match = result["row"], result["match"]
        if match["outcome"] != "completed" or row["status_extra"] != "FINISHED":
            continue
        mine = [(td.number(row[f"home_set_{n}_score"]), td.number(row[f"away_set_{n}_score"])) for n in range(1, 6)]
        mine = sum(a + b for a, b in mine if a is not None and b is not None)
        theirs = match_workload(match)["games"]
        games["equal" if theirs is not None and mine == theirs else "differ"] += 1
    out(f"   TennisData.app games (from set-by-set games) against Sackmann on linked completed matches: {dict(games)}")
    days = Counter()
    for row in td_open:
        days[row["day"].year] += 1
    out(f"   Match days exist only in TennisData.app rows (open main draw, by year: {dict(days)}) and TML 2026 round dates;"
        f" no source has match days before 2025, so rest days between matches cannot be learned from 2010-2023.")


def section_sealed(out):
    out("\n9. HELD-OUT PERIOD (metadata only: round labels and availability flags, in aggregate)")
    rows = tml.load_tml()
    editions = tml.editions(rows)
    candidates = [r for r in rows if r["sealed"] and editions[(r["tour"], r["tourney_id"])]["start"] >= td.HELD_OUT_START
                  and not editions[(r["tour"], r["tourney_id"])]["ongoing"]]
    kinds = Counter()
    for row in candidates:
        if row["tourney_level"] == "D":
            kind = "team tie"
        elif row["round"] == "RR":
            kind = "round robin"
        elif round_order(row["round"]) is None:
            kind = "unordered round"
        else:
            first = min(round_order(r["round"]) for r in rows if (r["tour"], r["tourney_id"]) == (row["tour"], row["tourney_id"])
                        and round_order(r["round"]))
            kind = "knockout, first round" if round_order(row["round"]) == first else "knockout, later round"
        kinds[(row["tour"], kind)] += 1
    out(f"   TML candidate rows by round type: {dict(sorted(kinds.items()))}")
    out(f"   TML candidate rows with all statistics (points available after unsealing): "
        f"{dict(Counter((r['tour'], r['has_all_stats']) for r in candidates))}. Minutes are sealed; their share is unknown "
        f"until the held-out command runs.")
    td_candidates, _ = td.held_out_candidates(td.load_provider(), SNAPSHOT)
    out(f"   TennisData.app candidate rows by round label: "
        f"{dict(sorted(Counter((r['tour'], r['round'] or 'blank') for r in td_candidates).items()))}. TennisData.app has "
        f"no minutes or point counts; games come from its set scores.")


def main():
    out = Output()
    out("Physical workload and route difficulty: focused audit. Coverage and structure only; no feature is related to")
    out("match outcomes here. Sealed rows are read through their readers and reported in aggregate.\n")
    matches = load_matches_with_workload()
    section_inputs(out, matches)
    section_plausibility(out, matches)
    section_correlation(out, matches)
    section_structure(out, matches)
    elo_run, surface_run = run_elo(matches, ELO_K), run_elo(matches, SURFACE_ELO_K)
    found = round_aware_features([m for m in matches if m["tourney_date"] >= 20090101], elo_run, surface_run)
    section_eligibility(out, matches, found)
    section_availability(out, matches, found)
    section_recent(out, matches)
    section_sources(out)
    section_sealed(out)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / "workload_audit.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    inputs = [p for tour in TOURS for p in match_files(tour)] + tml.tml_files() + td.provider_files()
    (AUDIT_DIR / "workload_audit_manifest.json").write_text(json.dumps(manifest("audit_workload", inputs), indent=2),
                                                            encoding="utf-8")
    print(f"\nWritten to {AUDIT_DIR / 'workload_audit.txt'}")


if __name__ == "__main__":
    main()

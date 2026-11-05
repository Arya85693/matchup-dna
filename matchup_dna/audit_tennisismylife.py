"""Data-quality audit of the TennisIsMyLife (TML) files, and how they overlap Sackmann and TennisData.app.

    python -m matchup_dna.audit_tennisismylife

Reads TML only through tennisismylife.load_tml() and TennisData.app only through tennisdata.load_provider(),
so rows from the held-out period arrive without winners, scores, or statistics. For those rows this program
counts metadata only, and prints aggregates only: no per-match listing of sealed rows, because the players
named in a later round would reveal who won the earlier ones. Writes results/phase4/audit/tml_audit.txt,
a manifest, and results/phase4/tml_crosswalk.csv (all gitignored).
"""
import csv
import datetime
import json
import statistics
from collections import Counter, defaultdict

from matchup_dna import serve_stats
from matchup_dna import tennisdata as td
from matchup_dna import tennisismylife as tml
from matchup_dna.audit_tennisdata import (
    AUDIT_DIR, column_type, link_population, load_rankings, ranking_lag, sackmann_overlap, share,
)
from matchup_dna.crosswalk import (
    build_links, full_name_key, initial_keys, link_pairs, load_player_names, provider_name_key,
    sackmann_pair_keys, to_day,
)
from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import Output, manifest
from matchup_dna.load import TOURS, match_outcome

CROSSWALK_PATH = RESULTS_DIR / "phase4" / "tml_crosswalk.csv"
SNAPSHOT = datetime.date(2026, 11, 5)
WINDOW = (-3, 16)  # TML date minus Sackmann tourney_date, or TennisData.app day minus TML date, in days


def tml_day(row):
    return to_day(int(row["tourney_date"]))


def winner_loser_keys(row):
    return full_name_key(row["winner_name"]), full_name_key(row["loser_name"])


def to_sackmann(items, matches, names):
    """Links open TML rows to Sackmann matches by both full names and the window, per tour."""
    results = []
    for tour in TOURS:
        results += link_pairs(
            [row for row in items if row["tour"] == tour], [m for m in matches if m["tour"] == tour],
            winner_loser_keys, sackmann_pair_keys(names),
            lambda row, match: WINDOW[0] <= (tml_day(row) - to_day(match["tourney_date"])).days <= WINDOW[1])
    return results


def tml_initial_options(row):
    """target_keys for TML rows when TennisData.app rows look for them: every surname-initial key of each name."""
    first, second = (("a_name", "b_name") if "a_name" in row else ("winner_name", "loser_name"))
    return [((x, y), "initials") for x in initial_keys(row[first]) for y in initial_keys(row[second])]


def td_to_tml_by_ids(td_rows, tml_rows, td_links, tml_links, taken=()):
    """Second pass for rows the names missed: both players of each row resolve to Sackmann ids through the
    validated crosswalks, the two Sackmann id pairs are equal, the day window holds, and the link is unique in
    both directions. Returns [(TennisData.app row, TML row)]."""
    by_pair = defaultdict(list)
    for row in tml_rows:
        if id(row) in taken:
            continue
        ids = [tml_links.get((row["tour"], player)) for player in tml.players(row)]
        if None not in ids and ids[0] != ids[1]:
            by_pair[(row["tour"], frozenset(ids))].append(row)
    found = []
    for row in td_rows:
        ids = (td_links.get((row["tour"], row["home_id"])), td_links.get((row["tour"], row["away_id"])))
        if None in ids:
            continue
        candidates = [target for target in by_pair.get((row["tour"], frozenset(ids)), ())
                      if WINDOW[0] <= (row["day"] - tml_day(target)).days <= WINDOW[1]]
        if len(candidates) == 1:
            found.append((row, candidates[0]))
    claims = Counter(id(target) for _, target in found)
    return [(row, target) for row, target in found if claims[id(target)] == 1]


def td_to_tml(td_rows, tml_rows):
    results = []
    for tour in TOURS:
        results += link_pairs(
            [row for row in td_rows if row["tour"] == tour], [row for row in tml_rows if row["tour"] == tour],
            lambda row: (provider_name_key(row["home_name"]), provider_name_key(row["away_name"])),
            tml_initial_options,
            lambda row, target: WINDOW[0] <= (row["day"] - tml_day(target)).days <= WINDOW[1])
    return results


# ---------------------------------------------------------------- sections

def section_files(out, rows):
    out("1. FILES")
    for name in tml.FILES:
        mine = [row for row in rows if row["source_file"] == name]
        dates = [int(row["tourney_date"]) for row in mine]
        sealed = sum(row["sealed"] for row in mine)
        out(f"   {name:<26} {len(mine):>5,} rows, {len(tml.EXPECTED_COLUMNS)} columns, tourney_date {min(dates)} to "
            f"{max(dates)}; open {len(mine) - sealed:,}, sealed {sealed:,}")
    from matchup_dna.load import DATA_DIR
    with open(DATA_DIR / "atp" / "atp_matches_2025.csv", encoding="utf-8") as file:
        sackmann_columns = next(csv.reader(file))
    extra = [c for c in tml.EXPECTED_COLUMNS if c not in sackmann_columns]
    missing = [c for c in sackmann_columns if c not in tml.EXPECTED_COLUMNS]
    out(f"   Against Sackmann's {len(sackmann_columns)} columns: extra {extra}, missing {missing or 'none'}; "
        f"same order: {[c for c in tml.EXPECTED_COLUMNS if c in sackmann_columns] == sackmann_columns}")


def section_columns(out, open_rows, sealed_rows):
    out("\n2. COLUMNS: inferred type and blank share on open rows; blank share on sealed rows where kept")
    for column in tml.EXPECTED_COLUMNS:
        values = [row[column].strip() for row in open_rows if row[column].strip()]
        kept = column if column in tml.METADATA_COLUMNS else None
        if column.startswith(("winner_", "loser_")) and column.split("_", 1)[1] in tml.PLAYER_FIELDS:
            kept = "a_" + column.split("_", 1)[1]
        sealed = (f"{sum(tml.blank(row[kept]) for row in sealed_rows) / len(sealed_rows):6.1%}" if kept
                  else "sealed")
        out(f"   {column:<20} {column_type(values):<12} {len(set(values)):>6,} distinct  blank "
            f"{1 - len(values) / len(open_rows):6.1%}   sealed rows: {sealed}")
    for flag in ("has_serve_stats", "has_all_stats"):
        out(f"   Sealed rows with {flag}: {dict(Counter((row['tour'], row[flag]) for row in sealed_rows))}")


def section_categories(out, rows):
    out("\n3. CATEGORIES (all rows; metadata)")
    out(f"   tourney_level: {dict(sorted(Counter((r['tour'], r['tourney_level']) for r in rows).items()))}")
    out(f"   round: {dict(Counter(r['round'] for r in rows).most_common())}")
    out(f"   surface: {dict(Counter(r['surface'] for r in rows))}; indoor: {dict(Counter(r['indoor'] for r in rows))}")
    out(f"   best_of: {dict(sorted(Counter((r['tour'], r['tourney_level'], r['best_of']) for r in rows).items()))}")
    entries = Counter(r[f"{p}_entry"] for r in rows for p in (("a", "b") if r["sealed"] else ("winner", "loser")))
    out(f"   entry codes: {dict(entries.most_common())}  (no qualifying rounds: rounds are main draw only)")


def section_dates(out, rows):
    out("\n4. DATES")
    by_round = defaultdict(set)
    for row in rows:
        by_round[(row["tour"], row["source_file"], row["tourney_id"])].add(row["tourney_date"])
    for name in tml.FILES:
        keys = [k for k in by_round if k[1] == name]
        multi = sum(len(by_round[k]) > 1 for k in keys)
        out(f"   {name:<26} {len(keys):>4} tournaments, {multi:>4} with more than one tourney_date across rounds")
    out("   The 2026 files date each round separately, so an edition's start is the earliest date on its rows.")


def section_integrity(out, rows, open_rows):
    out("\n5. INTEGRITY")
    keys = Counter((r["tour"], r["tourney_id"], r["match_num"]) for r in rows)
    pairs = Counter((r["tour"], r["tourney_id"], r["round"], tml.players(r)) for r in rows)
    out(f"   Repeated tour + tourney_id + match_num (all rows): {sum(c - 1 for c in keys.values() if c > 1)}")
    out(f"   Repeated tour + tourney_id + round + player pair (all rows): {sum(c - 1 for c in pairs.values() if c > 1)}")
    out(f"   Same id on both sides (all rows): {sum(len(set(tml.players(r))) == 1 for r in rows)}")
    seasons = {(r["tour"], r["tourney_id"]) for r in rows if not r["ongoing"]}
    ongoing = {(r["tour"], r["tourney_id"]) for r in rows if r["ongoing"]}
    out(f"   Tournaments in both a season file and an ongoing file: {len(seasons & ongoing)}")
    out(f"   Endings from the score (open rows): {dict(Counter((r['tour'], match_outcome(r['score'])) for r in open_rows))}")
    problems, lines = Counter(), Counter()
    for row in open_rows:
        for prefix in ("w", "l"):
            found = serve_stats.line_problems(serve_stats.stat_line(row, prefix))
            lines[(row["tour"], "complete and valid" if not found else
                   "all missing" if len([p for p in found if p.startswith("missing")]) == 9 else "has a problem")] += 1
            for problem in found:
                if not (len([p for p in found if p.startswith("missing")]) == 9 and problem.startswith("missing")):
                    problems[(row["tour"], problem)] += 1
    out(f"   Open player stat lines: {dict(sorted(lines.items()))}")
    for key, count in sorted(problems.items()):
        out(f"      {key}: {count}")
    walkovers = [r for r in open_rows if match_outcome(r["score"]) == "walkover"]
    out(f"   Walkovers with statistics (open): {sum(not tml.blank(r['w_svpt']) for r in walkovers)} of {len(walkovers)}")


def section_ids(out, rows):
    out("\n6. PLAYER IDS (all rows; metadata)")
    names, ids_of = defaultdict(set), defaultdict(set)
    for row in rows:
        for prefix in (("a", "b") if row["sealed"] else ("winner", "loser")):
            names[(row["tour"], row[f"{prefix}_id"])].add(row[f"{prefix}_name"])
            ids_of[(row["tour"], row[f"{prefix}_name"])].add(row[f"{prefix}_id"])
    for tour in TOURS:
        mine = [k[1] for k in names if k[0] == tour]
        out(f"   {tour}: {len(mine):,} ids; all digits {sum(i.isdigit() for i in mine):,}; with letters "
            f"{sum(not i.isdigit() for i in mine):,}")
    out(f"   Ids with more than one name: {[(k, sorted(v)) for k, v in names.items() if len(v) > 1]}")
    out(f"   Names with more than one id: {[(k, sorted(v)) for k, v in ids_of.items() if len(v) > 1]}")


def section_sackmann(out, open_rows, matches, names, rankings):
    out("\n7. LINKING OPEN ROWS TO SACKMANN (both full names, either name order, TML date minus Sackmann "
        f"tourney_date between {WINDOW[0]} and +{WINDOW[1]} days, one candidate, no match claimed twice)")
    results = to_sackmann(open_rows, matches, names)
    out(f"   {dict(sorted(Counter((r['item']['tour'], r['status']) for r in results).items()))}")
    linked = [r for r in results if r["status"] == "linked"]
    out(f"   Linked through a reversed name order: {sum(r['tag'] == 'reversed' for r in linked)}")
    out(f"   Unlinked, by tournament: {Counter(r['item']['tourney_name'] for r in results if r['status'] != 'linked').most_common(12)}")

    pairs = []
    for result in linked:
        row, match = result["item"], result["target"]
        winner, loser = (match["winner_id"], match["loser_id"]) if result["same_order"] else (
            match["loser_id"], match["winner_id"])
        pairs += [(row["tour"], row["winner_id"], winner), (row["tour"], row["loser_id"], loser)]
    crosswalk = build_links(pairs)
    single = sum(sum(c.values()) == 1 for k, c in crosswalk["support"].items() if k in crosswalk["links"])
    out(f"   Crosswalk: {len(crosswalk['support']):,} TML ids seen, {len(crosswalk['links']):,} accepted one-to-one, "
        f"{len(crosswalk['conflicts'])} conflicts; {single} accepted ids rest on one linked match")
    for conflict in crosswalk["conflicts"]:
        out(f"      conflict: {conflict}")
    wta = [(k, v) for k, v in crosswalk["links"].items() if k[0] == "WTA"]
    differ = [(k, v) for k, v in wta if k[1] != str(v)]
    out(f"   WTA TML ids equal to the Sackmann id: {share(len(wta) - len(differ), len(wta))}. Different:")
    for (tour, tml_id), sackmann_id in differ:
        person = names[(tour, sackmann_id)]
        out(f"      TML {tml_id} = Sackmann {sackmann_id} {person['first']} {person['last']}")

    found = {id(r["target"]) for r in linked}
    coverage = defaultdict(Counter)
    for match in matches:
        if match["tourney_date"] >= 20241229:
            coverage[(match["tour"], match["tourney_date"] // 10000, match["tourney_level"])][id(match) in found] += 1
    out("   Sackmann matches (weeks from 29 Dec 2024 to 25 May 2026) found in TML:")
    for key in sorted(coverage):
        out(f"      {key[0]} {key[1]} level {key[2]:<5} {share(coverage[key][True], sum(coverage[key].values()))}")

    out("\n8. AGREEMENT WITH SACKMANN ON LINKED MATCHES")
    tally, levels, gaps, serve_gap = Counter(), Counter(), Counter(), []
    ranks, _ = rankings
    for result in linked:
        row, match, raw = result["item"], result["target"], result["target"]["raw"]
        tally[("winner agrees", result["same_order"])] += 1
        if not result["same_order"]:
            continue
        tally[("score identical", row["score"] == match["score"])] += 1
        tally[("ending", match["outcome"] == match_outcome(row["score"]))] += 1
        tally[("surface", row["surface"] == (match["surface"] or ""))] += 1
        tally[("round", row["round"] == match["round"])] += 1
        tally[("best_of", row["best_of"] == str(match["best_of"]))] += 1
        levels[(row["tour"], row["tourney_level"], match["tourney_level"])] += 1
        gaps[(row["tour"], row["source_file"][:4], (tml_day(row) - to_day(match["tourney_date"])).days)] += 1
        for prefix, side in (("w", "winner"), ("l", "loser")):
            mine, theirs = row[f"{side}_rank"].strip(), raw[f"{side}_rank"].strip()
            if mine and theirs:
                tally[(f"{row['tour']} rank", "equal" if mine == theirs else
                       ranking_lag(ranks, row["tour"], match[f"{side}_id"], int(row["tourney_date"]), int(mine)))] += 1
            for field in serve_stats.STAT_FIELDS:
                mine, theirs = row[f"{prefix}_{field}"].strip(), raw[f"{prefix}_{field}"].strip()
                tally[(f"{field}", "identical" if mine and mine == theirs else "differ" if mine and theirs else
                       "TML only" if mine else "Sackmann only" if theirs else "neither")] += 1
            a = serve_stats.serve_points_won(serve_stats.stat_line(row, prefix))
            b = serve_stats.serve_points_won(serve_stats.stat_line(raw, prefix))
            if a and b:
                serve_gap.append(100 * a[0] / a[1] - 100 * b[0] / b[1])
    for key in sorted(tally, key=str):
        out(f"   {key}: {tally[key]:,}")
    if serve_gap:
        out(f"   Service points won %, TML minus Sackmann: within 1 point {share(sum(abs(g) <= 1 for g in serve_gap), len(serve_gap))}"
            f", identical {share(sum(g == 0 for g in serve_gap), len(serve_gap))}, sd {statistics.pstdev(serve_gap):.3f}")
    out(f"   Level codes (TML, Sackmann): {dict(sorted(levels.items()))}")
    editions = tml.editions(open_rows)
    starts = Counter()
    seen = set()
    for result in linked:
        row, match = result["item"], result["target"]
        edition = editions[(row["tour"], row["tourney_id"])]
        key = (row["tour"], row["tourney_id"], match["tourney_date"])
        if key not in seen:
            seen.add(key)
            starts[(row["source_file"][:4], (to_day(edition["start"]) - to_day(match["tourney_date"])).days)] += 1
    for year in ("2025", "2026"):
        values = {k[1]: v for k, v in starts.items() if k[0] == year}
        total = sum(values.values())
        out(f"   Edition start (earliest TML date) minus Sackmann tourney_date, {year} files, per edition: exact "
            f"{share(values.get(0, 0), total)}, within one day {share(sum(values.get(d, 0) for d in (-1, 0, 1)), total)};"
            f" {dict(sorted(values.items()))}")
    out("   TML date minus Sackmann tourney_date (days), by tour and file year:")
    for tour in TOURS:
        for year in ("2025", "2026"):
            values = {k[2]: v for k, v in gaps.items() if k[:2] == (tour, year)}
            out(f"      {tour} {year}: {dict(sorted(values.items()))}")
    return crosswalk, results


def section_tennisdata(out, tml_rows, td_rows, tml_to_sackmann, matches, names, tml_links):
    """Returns the TennisData.app crosswalk links for the held-out section."""
    out("\n9. TML AND TENNISDATA.APP")
    td_open = [r for r in td_rows if not r["sealed"] and td.is_main_draw(r)]
    tml_open = [r for r in tml_rows if not r["sealed"]]
    direct = td_to_tml(td_open, tml_open)
    td_linked, td_crosswalk, td_by_ids = link_population(td_open, matches, names)
    via_td = {td.row_key(r["row"]): id(r["match"]) for r in td_linked if r["status"] == "linked"}
    via_td.update({td.row_key(r["row"]): id(r["match"]) for r in td_by_ids})
    via_tml = {id(r["item"]): id(r["target"]) for r in tml_to_sackmann if r["status"] == "linked"}
    check = Counter()
    for result in direct:
        sackmann_td = via_td.get(td.row_key(result["item"]))
        if result["status"] == "linked":
            sackmann_tml = via_tml.get(id(result["target"]))
            if sackmann_td is not None and sackmann_tml is not None:
                check["direct link, both reach Sackmann: same match" if sackmann_td == sackmann_tml else
                      "direct link, both reach Sackmann: DIFFERENT match"] += 1
            else:
                check["direct link, at least one side not linked to Sackmann"] += 1
        elif sackmann_td is not None and sackmann_td in set(via_tml.values()):
            check[f"no direct link ({result['status']}) though both reach the same Sackmann match"] += 1
    out(f"   Open main-draw TennisData.app rows linked directly to TML rows (surname + initial against every split"
        f" of TML's full names, day window {WINDOW}):")
    out(f"   {dict(sorted(Counter((r['item']['tour'], r['status']) for r in direct).items()))}")
    out("   Checked against Sackmann, which both sources link to independently:")
    for key, count in sorted(check.items()):
        out(f"      {key}: {count:,}")
    taken = {id(r["target"]) for r in direct if r["status"] == "linked"}
    second = td_to_tml_by_ids([r["item"] for r in direct if r["status"] != "linked"], tml_open,
                              td_crosswalk["links"], tml_links, taken)
    verdict = Counter()
    for row, target in second:
        a, b = via_td.get(td.row_key(row)), via_tml.get(id(target))
        verdict["both reach Sackmann: same match" if a is not None and a == b else
                 "both reach Sackmann: DIFFERENT match" if a is not None and b is not None else
                 "at least one side not linked to Sackmann"] += 1
    out(f"   Second pass by validated player ids (TennisData.app and TML crosswalks): {len(second)} more links; "
        f"checked against Sackmann: {dict(verdict)}")
    paired = {id(r["item"]) for r in direct if r["status"] == "linked"} | {id(row) for row, _ in second}
    left = [r["item"] for r in direct if id(r["item"]) not in paired]
    out(f"   Open TennisData.app rows still without a TML row: {len(left):,}; by ending and whether Sackmann has the "
        f"match: {dict(Counter((r['status_extra'], td.row_key(r) in via_td) for r in left).most_common())}")
    tml_taken = {id(r["target"]) for r in direct if r["status"] == "linked"} | {id(t) for _, t in second}
    tml_left = [r for r in tml_open if id(r) not in tml_taken]
    out(f"   Open TML rows without a TennisData.app row: {len(tml_left):,}; by level: "
        f"{dict(Counter((r['tour'], r['tourney_level']) for r in tml_left).most_common())}")
    gap, filled = [], Counter()
    for result in direct:
        if result["status"] != "linked":
            continue
        row, target = result["item"], result["target"]
        for side, prefix in (("home", "w" if result["same_order"] else "l"), ("away", "l" if result["same_order"] else "w")):
            mine = serve_stats.serve_points_won(serve_stats.stat_line(target, prefix))
            theirs = td.number(row[f"{side}_service_points_won_perc"])
            if mine and theirs is not None:
                gap.append(theirs - 100 * mine[0] / mine[1])
            filled[("TML counts", mine is not None, "TennisData %", theirs is not None)] += 1
    if gap:
        out(f"   Service points won %, TennisData.app minus TML: within 1 point {share(sum(abs(g) <= 1 for g in gap), len(gap))}")
    out(f"   Player-matches by which source has serve statistics: {dict(filled)}")
    return td_crosswalk["links"]


def section_sealed(out, tml_rows, td_rows, tml_links, td_links):
    out("\n10. HELD-OUT PERIOD (metadata only)")
    sealed = [r for r in tml_rows if r["sealed"]]
    tml_editions = tml.editions(tml_rows)
    out(f"   TML sealed rows: {dict(Counter(r['tour'] for r in sealed))}; by level: "
        f"{dict(sorted(Counter((r['tour'], r['tourney_level']) for r in sealed).items()))}")
    early = Counter((r["tour"], tml_editions[(r["tour"], r["tourney_id"])]["name"]) for r in sealed
                    if tml_editions[(r["tour"], r["tourney_id"])]["start"] < td.HELD_OUT_START)
    out(f"   Sealed TML rows of editions that start before the held-out period (late rounds dated June): {dict(early)}")
    ongoing = [e for e in tml_editions.values() if e["ongoing"]]
    out(f"   Ongoing-file editions: {sorted((e['tour'], e['name'], e['start'], e['rows']) for e in ongoing)}")
    tml_candidates = [r for r in sealed if tml_editions[(r["tour"], r["tourney_id"])]["start"] >= td.HELD_OUT_START
                      and not tml_editions[(r["tour"], r["tourney_id"])]["ongoing"]]
    out(f"   TML candidate rows (edition starts 1 June 2026 or later, not in an ongoing file): "
        f"{dict(Counter(r['tour'] for r in tml_candidates))} in "
        f"{len({(r['tour'], r['tourney_id']) for r in tml_candidates})} tournaments (Davis Cup and BJK Cup count each tie)")

    td_candidates, by_match = td.held_out_candidates(td_rows, SNAPSHOT)
    out(f"   TennisData.app candidate rows: {dict(Counter(r['tour'] for r in td_candidates))}")
    links = td_to_tml(td_candidates, tml_candidates)
    out(f"   TennisData.app candidates linked to TML candidates: "
        f"{dict(sorted(Counter((r['item']['tour'], r['status']) for r in links).items()))}")
    taken = {id(r["target"]) for r in links if r["status"] == "linked"}
    second = td_to_tml_by_ids([r["item"] for r in links if r["status"] != "linked"], tml_candidates,
                              td_links, tml_links, taken)
    out(f"   Second pass by validated player ids: {dict(Counter(row['tour'] for row, _ in second))} more links")
    taken |= {id(target) for _, target in second}
    second_td = {id(row) for row, _ in second}
    tml_only = [r for r in tml_candidates if id(r) not in taken]
    td_only = [r["item"] for r in links if r["status"] != "linked" and id(r["item"]) not in second_td]
    out(f"   TennisData.app candidate rows with no TML row: {dict(Counter(r['tour'] for r in td_only))}; by players "
        f"in the TennisData.app crosswalk (0, 1, 2): "
        f"{dict(sorted(Counter((r['tour'], sum((r['tour'], r[s + '_id']) in td_links for s in td.SIDES)) for r in td_only).items()))}")
    out(f"   TML candidate rows with no TennisData.app row: {dict(Counter(r['tour'] for r in tml_only))}")
    out(f"      by level: {dict(sorted(Counter((r['tour'], r['tourney_level']) for r in tml_only).items()))}")
    out(f"      by tournament (largest): {Counter((r['tour'], r['tourney_name']) for r in tml_only).most_common(12)}")
    out(f"   TennisData.app candidate rows with no TML row, by tournament (largest): "
        f"{Counter((r['tour'], r['tournament']) for r in td_only).most_common(15)}")
    linked = [r for r in links if r["status"] == "linked"]
    out(f"   Linked pairs by serve statistics present (TML, TennisData.app): "
        f"{dict(Counter((r['item']['tour'], r['target']['has_serve_stats'], r['item']['has_serve_stats']) for r in linked))}")
    out(f"   TML candidate rows with serve statistics: {dict(Counter((r['tour'], r['has_serve_stats']) for r in tml_candidates))}")
    out(f"   TML candidate rows with all 18 statistics: {dict(Counter((r['tour'], r['has_all_stats']) for r in tml_candidates))}")
    known = Counter((r["tour"], sum((r["tour"], r[f"{p}_id"]) in tml_links for p in ("a", "b"))) for r in tml_candidates)
    out(f"   TML candidate rows by players in the TML-Sackmann crosswalk (0, 1, 2): {dict(sorted(known.items()))}")
    union = Counter(r["tour"] for r in tml_candidates) + Counter(r["tour"] for r in td_only)
    out(f"   Union of the two sources (TML rows plus TennisData.app rows not in TML): {dict(union)}")
    out("   These are upper bounds on held-out matches: endings stay sealed.")


def main():
    out = Output()
    rows = tml.load_tml()
    open_rows = [r for r in rows if not r["sealed"]]
    sealed_rows = [r for r in rows if r["sealed"]]
    out("TennisIsMyLife audit. Rows dated 1 June 2026 or later were read through the seal: no winner, score, or")
    out("statistic of those rows is available to this program, and sealed rows are reported in aggregate only.\n")
    section_files(out, rows)
    section_columns(out, open_rows, sealed_rows)
    section_categories(out, rows)
    section_dates(out, rows)
    section_integrity(out, rows, open_rows)
    section_ids(out, rows)
    matches, names = sackmann_overlap(), load_player_names()
    crosswalk, tml_to_sackmann = section_sackmann(out, open_rows, matches, names, load_rankings())
    td_rows = td.load_provider()
    td_links = section_tennisdata(out, rows, td_rows, tml_to_sackmann, matches, names, crosswalk["links"])
    section_sealed(out, rows, td_rows, crosswalk["links"], td_links)

    CROSSWALK_PATH.parent.mkdir(parents=True, exist_ok=True)
    tml_names = defaultdict(set)
    for row in rows:
        for prefix in (("a", "b") if row["sealed"] else ("winner", "loser")):
            tml_names[(row["tour"], row[f"{prefix}_id"])].add(row[f"{prefix}_name"])
    with open(CROSSWALK_PATH, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["tour", "tml_id", "sackmann_id", "sackmann_name", "tml_names", "linked_matches"])
        for (tour, tml_id), sackmann_id in sorted(crosswalk["links"].items()):
            person = names[(tour, sackmann_id)]
            writer.writerow([tour, tml_id, sackmann_id, f"{person['first']} {person['last']}",
                             "; ".join(sorted(tml_names[(tour, tml_id)])), crosswalk["support"][(tour, tml_id)][sackmann_id]])
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / "tml_audit.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    record = manifest("audit_tennisismylife", tml.tml_files() + td.provider_files() + [CROSSWALK_PATH],
                      {"seal_date": tml.SEAL_DATE, "sealed_columns_removed": list(tml.OUTCOME_COLUMNS)})
    (AUDIT_DIR / "tml_audit_manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"\nWritten to {AUDIT_DIR / 'tml_audit.txt'} and {CROSSWALK_PATH}")


if __name__ == "__main__":
    main()

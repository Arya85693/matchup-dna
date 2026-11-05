"""Data-quality audit of the TennisData.app season files.

    python -m matchup_dna.audit_tennisdata

Reads the provider files only through tennisdata.load_provider(), so rows dated 1 June 2026 or later arrive
without outcome, score, odds, or statistic columns. Everything about those rows below is metadata. Writes
results/phase4/audit/tennisdata_audit.txt, a manifest, and results/phase4/crosswalk.csv (all gitignored).
"""
import csv
import datetime
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from matchup_dna import tennisdata as td
from matchup_dna.crosswalk import (
    build_crosswalk, link_by_ids, link_matches, load_player_names, pair_ids, provider_name_key, save_crosswalk,
)
from matchup_dna.elo import RESULTS_DIR
from matchup_dna.experiment import Output, manifest
from matchup_dna.load import DATA_DIR, TOURS, match_files, match_outcome, parse_match

AUDIT_DIR = RESULTS_DIR / "phase4" / "audit"
CROSSWALK_PATH = RESULTS_DIR / "phase4" / "crosswalk.csv"
OVERLAP_START = 20241201
SACKMANN_LAST_WEEK = 20260525
ELIGIBLE_SHARE = 0.5


# ---------------------------------------------------------------- inputs

def sackmann_overlap(data_dir=DATA_DIR):
    """Sackmann tour-level matches from December 2024 on, each with its raw CSV row under "raw"."""
    matches = []
    for tour in TOURS:
        for path in match_files(tour, data_dir):
            if int(path.stem[-4:]) < 2024:
                continue
            with open(path, encoding="utf-8", newline="") as file:
                for row in csv.DictReader(file):
                    match = parse_match(row, tour)
                    if match["tourney_date"] >= OVERLAP_START:
                        match["raw"] = row
                        matches.append(match)
    return matches


def load_rankings(data_dir=DATA_DIR, start=20241101):
    """{(tour, player_id): [(ranking_date, rank)]} sorted by date, and each tour's sorted ranking dates."""
    ranks, dates = defaultdict(list), defaultdict(set)
    for tour in TOURS:
        for name in ("20s", "current"):
            path = Path(data_dir) / tour.lower() / f"{tour.lower()}_rankings_{name}.csv"
            with open(path, encoding="utf-8", newline="") as file:
                for row in csv.DictReader(file):
                    date = int(row["ranking_date"])
                    if date >= start:
                        ranks[(tour, int(row["player"]))].append((date, int(row["rank"])))
                        dates[tour].add(date)
    for value in ranks.values():
        value.sort()
    return ranks, {tour: sorted(values) for tour, values in dates.items()}


def rank_on(ranks, tour, player, date):
    """The player's rank on the latest ranking date on or before `date` (YYYYMMDD), or None."""
    found = None
    for ranking_date, rank in ranks.get((tour, player), ()):
        if ranking_date > date:
            break
        found = rank
    return found


def ranking_lag(ranks, tour, player, day, rank):
    """Label for where a provider rank sits in the official ranking history: "lag -1 week" etc."""
    history = ranks.get((tour, player), ())
    hits = [date for date, value in history if value == rank]
    if not hits:
        return "differs; rank on no ranking list"
    before = [date for date, _ in history if date <= day]
    base = max(before) if before else history[0][0]

    def weeks(date):
        return (datetime.date(date // 10000, date // 100 % 100, date % 100)
                - datetime.date(base // 10000, base // 100 % 100, base % 100)).days // 7

    nearest = min(hits, key=lambda date: abs(weeks(date)))
    return f"differs; nearest list {weeks(nearest):+d} weeks"


def ymd(day):
    return int(day.strftime("%Y%m%d"))


def share(part, whole):
    return f"{part:,}/{whole:,} ({part / whole:.1%})" if whole else f"{part}/0"


# ---------------------------------------------------------------- sections

def section_files(out, rows, paths):
    out("1. FILES")
    for path in paths:
        mine = [row for row in rows if row["source_file"] == path.name]
        sealed = sum(row["sealed"] for row in mine)
        days = [row["day"] for row in mine]
        out(f"   {path.name:<22} {len(mine):>6,} rows, {len(td.EXPECTED_COLUMNS)} columns, match days {min(days)} "
            f"to {max(days)}; before 1 June 2026: {len(mine) - sealed:,}; sealed: {sealed:,}; "
            f"season_year {sorted(set(row['season_year'] for row in mine))}")
    snapshot = max(datetime.date.fromtimestamp(path.stat().st_mtime) for path in paths)
    out(f"   Files last modified {snapshot}; rows dated on or after that day: "
        f"{sum(row['day'] >= snapshot for row in rows):,}")
    return snapshot


def column_type(values):
    if not values:
        return "always blank"
    try:
        numbers = [float(value) for value in values]
    except ValueError:
        return "text"
    return "integer" if all(number.is_integer() and "." not in value for number, value in zip(numbers, values)) \
        else "decimal"


def section_columns(out, open_rows, sealed_rows):
    out("\n2. COLUMNS: inferred type, distinct values, and blank share (open rows; sealed rows where not sealed)")
    for column in td.EXPECTED_COLUMNS:
        values = [row[column].strip() for row in open_rows if row[column].strip() != ""]
        blank = 1 - len(values) / len(open_rows)
        sealed_part = "sealed" if column in td.SEALED_COLUMNS else (
            f"{sum(row[column].strip() == '' for row in sealed_rows) / len(sealed_rows):.1%}")
        out(f"   {column:<32} {column_type(values):<12} {len(set(values)):>7,} distinct  blank {blank:6.1%}"
            f"   sealed rows blank: {sealed_part}")


def section_values(out, rows, open_rows):
    out("\n3. CATEGORIES")
    out(f"   tour_type (all rows): {dict(Counter((row['tour_type'], row['tour_type_human']) for row in rows))}")
    out(f"   surface (all rows): {dict(Counter(row['surface'] for row in rows))}")
    out(f"   round (all rows): {dict(Counter(row['round'] for row in rows).most_common())}")
    kinds = Counter((row["tour"], row["circuit"], "qualifying" if row["qualifying"] else
                     "wheelchair" if row["wheelchair"] else "main draw") for row in rows)
    out("   Rows by tour, circuit, and draw (all rows):")
    for key, count in sorted(kinds.items()):
        out(f"      {key}: {count:,}")
    out(f"   status / status_extra (open rows only): "
        f"{dict(Counter((row['status'], row['status_extra']) for row in open_rows).most_common())}")


def section_integrity(out, rows, open_rows):
    out("\n4. INTEGRITY (open rows unless stated)")
    ids = Counter(row["match_id"] for row in rows)
    within = Counter(td.row_key(row) for row in rows)
    out(f"   match_id values used twice (all rows): {sum(count - 1 for count in ids.values() if count > 1)}; "
        f"twice within one tour: {sum(count - 1 for count in within.values() if count > 1)}. A reused match_id is")
    out("   a different ATP and WTA match, so a provider match is identified by tour plus match_id.")
    pairs = Counter((row["tour"], row["day"], frozenset((row["home_id"], row["away_id"]))) for row in rows)
    out(f"   Rows repeating tour + day + player pair (all rows): {sum(c - 1 for c in pairs.values() if c > 1)}")
    out(f"   Same id on both sides (all rows): {sum(row['home_id'] == row['away_id'] for row in rows)}")

    complement, bp_complement, out_of_range, negative = Counter(), Counter(), 0, 0
    for row in open_rows:
        for a, b in (("home", "away"), ("away", "home")):
            serve, ret = td.number(row[f"{a}_service_points_won_perc"]), td.number(row[f"{b}_return_points_won_perc"])
            if serve is not None and ret is not None:
                complement[abs(serve + ret - 100) <= 1] += 1
            won, saved = td.number(row[f"{a}_break_points_won_perc"]), td.number(row[f"{b}_break_points_saved_perc"])
            if won is not None and saved is not None:
                bp_complement[abs(won + saved - 100) <= 1] += 1
        for column in td.STAT_COLUMNS:
            value = td.number(row[column])
            if value is None:
                continue
            if column.endswith("_perc") and not 0 <= value <= 100:
                out_of_range += 1
            if value < 0:
                negative += 1
    out(f"   Serve points won % + opponent return points won % = 100 (+-1): {share(complement[True], sum(complement.values()))}")
    out(f"   BP won % + opponent BP saved % = 100 (+-1): {share(bp_complement[True], sum(bp_complement.values()))}")
    out(f"   Percentages outside 0-100: {out_of_range}; negative statistics: {negative}")

    finished = [row for row in open_rows if row["status_extra"] == "FINISHED"]
    winner_vs_sets, sets_vs_games = Counter(), Counter()
    for row in finished:
        home, away = td.number(row["home_set_score"]), td.number(row["away_set_score"])
        if row["winner_code"] in ("1", "2") and home is not None and away is not None:
            winner_vs_sets[(home > away) == (row["winner_code"] == "1")] += 1
        games = [(td.number(row[f"home_set_{n}_score"]), td.number(row[f"away_set_{n}_score"])) for n in range(1, 6)]
        games = [(h, a) for h, a in games if h is not None and a is not None]
        if games and home is not None:
            sets_vs_games[(sum(h > a for h, a in games), sum(a > h for h, a in games)) == (home, away)] += 1
    out(f"   FINISHED rows: winner_code agrees with sets won {share(winner_vs_sets[True], sum(winner_vs_sets.values()))}; "
        f"sets won agree with set-by-set games {share(sets_vs_games[True], sum(sets_vs_games.values()))}")
    by_status = defaultdict(Counter)
    for row in open_rows:
        by_status[row["status_extra"]]["rows"] += 1
        by_status[row["status_extra"]]["winner code blank"] += row["winner_code"] == ""
        by_status[row["status_extra"]]["serve stats present"] += row["home_service_points_won_perc"].strip() != ""
    for status, counts in sorted(by_status.items()):
        out(f"   {status:<9}: {dict(counts)}")

    names, ids_of = defaultdict(set), defaultdict(set)
    for row in rows:
        for side in td.SIDES:
            names[(row["tour"], row[f"{side}_id"])].add(row[f"{side}_name"])
            ids_of[(row["tour"], row[f"{side}_name"])].add(row[f"{side}_id"])
    multi_name = {k: sorted(v) for k, v in names.items() if len(v) > 1}
    multi_id = {k: sorted(v) for k, v in ids_of.items() if len(v) > 1}
    out(f"   Provider ids with more than one name spelling (all rows): {len(multi_name)}")
    for key, value in sorted(multi_name.items()):
        out(f"      {key}: {value}")
    out(f"   Names carried by more than one provider id (all rows): {len(multi_id)}")
    for key, value in sorted(multi_id.items()):
        out(f"      {key}: {value}")

    ranks = defaultdict(set)
    for row in open_rows:
        for side in td.SIDES:
            if row[f"{side}_rank"].strip():
                ranks[(row["tour"], row["season_year"], row[f"{side}_id"])].add(row[f"{side}_rank"])
    for tour in TOURS:
        for year in ("2025", "2026"):
            sizes = [len(v) for k, v in ranks.items() if k[:2] == (tour, year)]
            season = [row for row in open_rows if (row["tour"], row["season_year"]) == (tour, year)]
            blank = sum(row[f"{side}_rank"].strip() == "" for row in season for side in td.SIDES) / (2 * len(season))
            out(f"   Ranks {tour} {year}: blank {blank:.1%}; {len(sizes):,} ranked players, "
                f"{sum(n > 1 for n in sizes) / len(sizes):.1%} of them with more than one rank value in the season")


def link_population(rows, matches, names):
    linked = link_matches(rows, matches, names)
    crosswalk = build_crosswalk(linked)
    taken = {id(result["match"]) for result in linked if result["status"] == "linked"}
    missed = [result["row"] for result in linked if result["status"] != "linked"]
    by_ids = link_by_ids(missed, matches, crosswalk["links"], taken=taken)
    return linked, crosswalk, by_ids


def section_linking(out, open_rows, matches, names):
    out("\n5. LINKING TO SACKMANN (open rows; Sackmann tour-level files from December 2024)")
    out("   Rule: same tour, normalized full surname + first initial for both players, provider day minus Sackmann")
    out("   tourney_date between -3 and +16 days, exactly one candidate, and no Sackmann match claimed twice.")
    main = [row for row in open_rows if td.is_main_draw(row)]
    linked, crosswalk, by_ids = link_population(main, matches, names)
    counts = Counter((row["tour"], result["status"]) for result in linked for row in (result["row"],))
    out(f"   Main-draw rows: {len(main):,}. Results: {dict(sorted(counts.items()))}")
    out(f"   Linked through a reversed-order name key: {sum(r['reversed'] for r in linked if r['status'] == 'linked')}")
    out(f"   Rows linked in a second pass by validated ids only (name spelling differs): {len(by_ids)}")
    for result in by_ids[:10]:
        row = result["row"]
        match = result["match"]
        out(f"      {row['day']} {row['tournament']}: {row['home_name']} / {row['away_name']} -> "
            f"{match['winner_name']} / {match['loser_name']}")
    second = {td.row_key(result["row"]) for result in by_ids}
    unmatched = Counter(result["row"]["tournament"] for result in linked
                        if result["status"] != "linked" and td.row_key(result["row"]) not in second)
    out("   Tournaments with the most unlinked main-draw rows:")
    for name, count in unmatched.most_common(15):
        out(f"      {name}: {count}")

    for label, subset in (("qualifying", [r for r in open_rows if r["circuit"] == "tour" and r["qualifying"]]),
                          ("Challenger / WTA 125", [r for r in open_rows if r["circuit"] == "challenger"])):
        results = link_matches(subset, matches, names)
        bad = [r for r in results if r["status"] == "linked"]
        out(f"   Control, {label} rows ({len(subset):,}), which Sackmann's tour-level files do not contain: "
            f"{len(bad)} would link by name and window. These are the same two players meeting in a main draw")
        out(f"      within the window, which is why only main-draw rows are linked.")

    out(f"\n   Crosswalk: {len(crosswalk['support']):,} provider ids seen in linked matches, {len(crosswalk['links']):,} "
        f"accepted one-to-one, {len(crosswalk['conflicts'])} conflicts left out")
    single = sum(sum(counts.values()) == 1 for key, counts in crosswalk["support"].items()
                 if key in crosswalk["links"])
    out(f"   Accepted ids supported by a single linked match: {single}")
    for conflict in crosswalk["conflicts"]:
        out(f"      conflict: {conflict}")
        for sackmann_id in conflict["sackmann_ids"]:
            person = names[(conflict["tour"], sackmann_id)]
            out(f"         Sackmann {sackmann_id} = {person['first']} {person['last']}")
    return linked, crosswalk, by_ids


def side_of(result, side):
    """("w" or "l") prefix in Sackmann's raw columns for the provider's home or away player."""
    winner_side = "home" if result["home"] == "winner" else "away"
    return "w" if side == winner_side else "l"


def sackmann_serve(raw, prefix):
    try:
        points = int(float(raw[f"{prefix}_svpt"]))
        won = int(float(raw[f"{prefix}_1stWon"])) + int(float(raw[f"{prefix}_2ndWon"]))
    except ValueError:
        return None
    return 100 * won / points if points > 0 else None


def sackmann_sets(score):
    """[(winner games, loser games)] for each set in a Sackmann score, ignoring tiebreak points."""
    sets = []
    for token in score.split():
        if "-" not in token:
            continue
        left, right = token.split("-", 1)
        left, right = left.split("(")[0], right.split("(")[0]
        if left.isdigit() and right.isdigit():
            sets.append((int(left), int(right)))
    return sets


def section_agreement(out, linked, by_ids, rankings):
    out("\n6. AGREEMENT WITH SACKMANN ON LINKED MAIN-DRAW MATCHES (open rows)")
    results = [r for r in linked if r["status"] == "linked"] + by_ids
    ranks, _ = rankings
    tally, serve_gaps, rank_detail, rank_month = Counter(), [], Counter(), defaultdict(Counter)
    for result in results:
        row, match, raw = result["row"], result["match"], result["match"]["raw"]
        if row["winner_code"] in ("1", "2"):
            tally[("winner agrees", (row["winner_code"] == "1") == (result["home"] == "winner"))] += 1
        tally[("ending", match["outcome"], row["status_extra"])] += 1
        provider_surface, sackmann_surface = row["surface"].lower(), (match["surface"] or "").lower()
        tally[("surface", "agrees" if provider_surface == sackmann_surface else
               f"provider {provider_surface} / Sackmann {sackmann_surface or 'blank'}")] += 1
        tally[("best_of", td.best_of(row) == match["best_of"])] += 1
        tally[("round", td.ROUNDS.get(row["round"], "?") == match["round"] or
               f"{row['round'] or 'blank'} / {match['round']}")] += 1
        if match["outcome"] == "completed" and row["status_extra"] == "FINISHED":
            mine = []
            for n in range(1, 6):
                h, a = td.number(row[f"home_set_{n}_score"]), td.number(row[f"away_set_{n}_score"])
                if h is not None and a is not None:
                    mine.append((int(h), int(a)) if result["home"] == "winner" else (int(a), int(h)))
            tally[("set games exact", mine == sackmann_sets(match["score"]))] += 1
        for side in td.SIDES:
            prefix = side_of(result, side)
            other = "l" if prefix == "w" else "w"
            for field, column in (("aces", "ace"), ("double_faults", "df")):
                mine, theirs = td.number(row[f"{side}_{field}"]), raw[f"{prefix}_{column}"].strip()
                if mine is not None and theirs:
                    tally[(f"{field} exact", mine == float(theirs))] += 1
            mine, theirs = td.number(row[f"{side}_service_points_won_perc"]), sackmann_serve(raw, prefix)
            if mine is not None and theirs is not None:
                serve_gaps.append(mine - theirs)
            mine, theirs = td.number(row[f"{side}_return_points_won_perc"]), sackmann_serve(raw, other)
            if mine is not None and theirs is not None:
                tally[("return points won % within 1", abs(mine - (100 - theirs)) <= 1)] += 1
            tally[("stats present (Sackmann, provider)", raw[f"{prefix}_svpt"].strip() != "",
                   row[f"{side}_service_points_won_perc"].strip() != "")] += 1
            try:
                faced, saved = int(float(raw[f"{prefix}_bpFaced"])), int(float(raw[f"{prefix}_bpSaved"]))
                mine = td.number(row[f"{side}_break_points_saved_perc"])
                if mine is not None and faced > 0:
                    tally[("BP saved % within 1 (Sackmann faced > 0)", abs(mine - 100 * saved / faced) <= 1)] += 1
                if mine is not None and faced == 0:
                    tally[("provider BP saved % when Sackmann faced 0", mine)] += 1
                opp_faced, opp_saved = int(float(raw[f"{other}_bpFaced"])), int(float(raw[f"{other}_bpSaved"]))
                mine = td.number(row[f"{side}_break_points_won_perc"])
                if mine is not None and opp_faced > 0:
                    tally[("BP won % within 1 (chances > 0)", abs(mine - 100 * (opp_faced - opp_saved) / opp_faced) <= 1)] += 1
                if mine is not None and opp_faced == 0:
                    tally[("provider BP won % when Sackmann chances 0", mine)] += 1
            except ValueError:
                pass
            provider_rank = td.number(row[f"{side}_rank"])
            sackmann_rank = match[f"{'winner' if prefix == 'w' else 'loser'}_rank"]
            player = match[f"{'winner' if prefix == 'w' else 'loser'}_id"]
            if provider_rank is not None and sackmann_rank is not None:
                equal = provider_rank == sackmann_rank
                rank_month[(row["tour"], row["day"].strftime("%Y-%m"))][equal] += 1
                if equal:
                    rank_detail[(row["tour"], "equal to Sackmann")] += 1
                else:
                    rank_detail[(row["tour"], ranking_lag(ranks, row["tour"], player, ymd(row["day"]),
                                                          int(provider_rank)))] += 1
    for key in sorted(tally, key=str):
        out(f"   {key}: {tally[key]:,}")
    if serve_gaps:
        within = sum(abs(gap) <= 1 for gap in serve_gaps)
        out(f"   Service points won %, provider minus Sackmann: {share(within, len(serve_gaps))} within 1 point; "
            f"mean {statistics.mean(serve_gaps):+.3f}, sd {statistics.pstdev(serve_gaps):.3f}, "
            f"{sum(abs(g) > 5 for g in serve_gaps)} differ by more than 5 points")
    out("   Ranks: provider rank vs Sackmann's rank on the match. When they differ, the official ranking list (Sackmann")
    out("   ranking files) nearest in time that shows the provider's rank, in weeks relative to the last list published")
    out("   on or before the match day. Negative means the provider's rank is older; positive would mean a later list:")
    for key in sorted(rank_detail):
        out(f"      {key}: {rank_detail[key]:,}")
    out("   Provider rank equal to Sackmann rank, by month:")
    for key in sorted(rank_month):
        out(f"      {key[0]} {key[1]}: {share(rank_month[key][True], sum(rank_month[key].values()))}")


def section_coverage(out, matches, linked, by_ids):
    out("\n7. SACKMANN MATCHES FOUND IN THE PROVIDER FILES (Sackmann weeks 27 Dec 2024 to 25 May 2026)")
    found = {id(r["match"]) for r in linked if r["status"] == "linked"} | {id(r["match"]) for r in by_ids}
    table = defaultdict(Counter)
    for match in matches:
        if match["tourney_date"] >= 20241227:
            table[(match["tour"], match["tourney_date"] // 10000, match["tourney_level"])][id(match) in found] += 1
    for key in sorted(table):
        out(f"   {key[0]} {key[1]} level {key[2]:<5} {share(table[key][True], sum(table[key].values()))}")


def linked_matches(linked, by_ids):
    """{(tour, provider match_id): Sackmann match} for every linked row, from either pass."""
    found = {td.row_key(r["row"]): r["match"] for r in linked if r["status"] == "linked"}
    found.update({td.row_key(r["row"]): r["match"] for r in by_ids})
    return found


def tournament_mapping(open_rows, linked, by_ids):
    """{(tour, tournament): {"rows", "linked", "levels", "share"}} for open main-draw rows."""
    found = linked_matches(linked, by_ids)
    mapping = defaultdict(lambda: {"rows": 0, "linked": 0, "levels": Counter(), "names": Counter()})
    for row in open_rows:
        if not td.is_main_draw(row):
            continue
        entry = mapping[(row["tour"], row["tournament"])]
        entry["rows"] += 1
        match = found.get(td.row_key(row))
        if match is not None:
            entry["linked"] += 1
            entry["levels"][match["tourney_level"]] += 1
            entry["names"][match["tourney_name"]] += 1
    for entry in mapping.values():
        entry["share"] = entry["linked"] / entry["rows"]
    return mapping


def section_tournaments(out, rows, open_rows, linked, by_ids, mapping):
    out(f"\n8. TOURNAMENTS AND WEEKS (open main-draw rows). A tournament name is in Sackmann's population when at least "
        f"{ELIGIBLE_SHARE:.0%} of its rows link.")
    validated = [key for key, entry in mapping.items() if entry["share"] >= ELIGIBLE_SHARE]
    out(f"   {len(mapping)} tournament names, {len(validated)} validated. Names below the threshold:")
    for key, entry in sorted(mapping.items()):
        if entry["share"] < ELIGIBLE_SHARE:
            out(f"      {key[0]} {key[1]:<62} {share(entry['linked'], entry['rows'])}  levels {dict(entry['levels'])}")

    main_rows = [row for row in rows if td.is_main_draw(row)]
    by_match = td.editions(main_rows)
    found = linked_matches(linked, by_ids)
    rules = {
        "first main-draw day (used)": lambda day: day,
        "Monday of that week, weekend starts to the next Monday": lambda day: day - datetime.timedelta(
            days=day.weekday()) if day.weekday() <= 4 else day + datetime.timedelta(days=7 - day.weekday()),
    }
    out("   Edition tourney_date rules against Sackmann's tourney_date, one count per linked edition and Sackmann date:")
    for label, rule in rules.items():
        gaps, examples, seen = Counter(), defaultdict(list), set()
        for row in open_rows:
            match = found.get(td.row_key(row))
            if match is None:
                continue
            edition = by_match[td.row_key(row)]
            key = (edition["tour"], edition["name"], edition["first_day"], match["tourney_date"])
            if key in seen:
                continue
            seen.add(key)
            sackmann = match["tourney_date"]
            gap = (rule(edition["first_day"]) - datetime.date(sackmann // 10000, sackmann // 100 % 100,
                                                              sackmann % 100)).days
            gaps[gap] += 1
            if gap:
                examples[gap].append(f"{edition['name']}: first day {edition['first_day']} "
                                     f"({edition['first_day']:%a}), Sackmann {sackmann}")
        total = sum(gaps.values())
        out(f"   {label}: exact {share(gaps[0], total)}, within one day "
            f"{share(gaps[-1] + gaps[0] + gaps[1], total)}; days off {dict(sorted(gaps.items()))}")
        if label.startswith("first"):
            for gap, items in sorted(examples.items()):
                for item in items[:5]:
                    out(f"      {gap:+d}: {item}")
    return by_match


def section_sealed(out, rows, crosswalk, mapping, by_match, snapshot):
    sealed = [row for row in rows if row["sealed"]]
    out("\n9. SEALED ROWS, 1 JUNE 2026 ONWARD (metadata only; outcome, score, odds and statistic columns removed)")
    columns = sorted(set().union(*(row.keys() for row in sealed)))
    out(f"   Columns available on sealed rows: {columns}")
    leaked = [column for column in td.SEALED_COLUMNS if any(column in row for row in sealed)]
    out(f"   Sealed columns present on any sealed row: {leaked or 'none'}")
    out(f"   Rows by month and circuit: "
        f"{dict(sorted(Counter((row['day'].strftime('%Y-%m'), row['tour'], row['circuit']) for row in sealed).items()))}")
    main = [row for row in sealed if td.is_main_draw(row)]
    out(f"   Main-draw rows: {dict(Counter(row['tour'] for row in main))}")

    status = Counter()
    candidates = []
    for row in main:
        edition = by_match[td.row_key(row)]
        if edition["tourney_date"] <= 20260531:
            status[(row["tour"], f"edition starts {edition['tourney_date']}, before the held-out period",
                    edition["name"])] += 1
        elif edition["last_day"] >= snapshot:
            status[(row["tour"], "edition still running at the file snapshot", edition["name"])] += 1
        else:
            candidates.append(row)
    for key, count in sorted(status.items()):
        out(f"   Excluded: {key}: {count}")
    validated = {key for key, entry in mapping.items() if entry["share"] >= ELIGIBLE_SHARE}
    known = set(mapping)
    names = Counter()
    for row in candidates:
        key = (row["tour"], row["tournament"])
        names[(row["tour"], "validated" if key in validated else "seen, below threshold" if key in known else "new name")] += 1
    out(f"   Candidate rows (edition starts 1 June 2026 or later, complete before {snapshot}): "
        f"{dict(Counter(row['tour'] for row in candidates))}")
    out(f"   Candidate rows by tournament-name status: {dict(sorted(names.items()))}")
    for tour in TOURS:
        new = sorted({row["tournament"] for row in candidates if row["tour"] == tour
                      and (tour, row["tournament"]) not in validated})
        out(f"   {tour} candidate tournament names not validated on the overlap: {new}")
    known_players = Counter((row["tour"], sum((row["tour"], row[f"{side}_id"]) in crosswalk["links"] for side in td.SIDES))
                            for row in candidates)
    out(f"   Candidate rows by players already in the crosswalk (0, 1, 2): {dict(sorted(known_players.items()))}")
    out(f"   Candidate rows with serve statistics present: "
        f"{dict(Counter((row['tour'], row['has_serve_stats']) for row in candidates))}")
    out("   This is an upper bound on held-out matches: status (completed, retired, walkover) stays sealed.")


def main():
    out = Output()
    paths = td.provider_files()
    rows = td.load_provider()
    open_rows = [row for row in rows if not row["sealed"]]
    sealed_rows = [row for row in rows if row["sealed"]]
    out("TennisData.app audit. Rows dated 1 June 2026 or later were read through the seal: no outcome, score, odds,")
    out("or statistic value of those rows is available to this program.\n")
    snapshot = section_files(out, rows, paths)
    section_columns(out, open_rows, sealed_rows)
    section_values(out, rows, open_rows)
    section_integrity(out, rows, open_rows)

    matches = sackmann_overlap()
    names = load_player_names()
    linked, crosswalk, by_ids = section_linking(out, open_rows, matches, names)
    section_agreement(out, linked, by_ids, load_rankings())
    section_coverage(out, matches, linked, by_ids)
    mapping = tournament_mapping(open_rows, linked, by_ids)
    by_match = section_tournaments(out, rows, open_rows, linked, by_ids, mapping)
    section_sealed(out, rows, crosswalk, mapping, by_match, snapshot)

    provider_names = defaultdict(set)
    for row in rows:
        for side in td.SIDES:
            provider_names[(row["tour"], row[f"{side}_id"])].add(row[f"{side}_name"])
    save_crosswalk(CROSSWALK_PATH, crosswalk, names, provider_names)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / "tennisdata_audit.txt").write_text("\n".join(out.lines) + "\n", encoding="utf-8")
    record = manifest("audit_tennisdata", paths + [CROSSWALK_PATH], {
        "sealed_from": str(td.SEAL_START), "sealed_columns_removed": list(td.SEALED_COLUMNS),
        "validated_tournaments": sorted(f"{k[0]}|{k[1]}" for k, v in mapping.items() if v["share"] >= ELIGIBLE_SHARE),
    })
    (AUDIT_DIR / "tennisdata_audit_manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"\nWritten to {AUDIT_DIR} and {CROSSWALK_PATH}")


if __name__ == "__main__":
    main()

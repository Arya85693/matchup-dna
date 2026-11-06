"""Assembling matches after Sackmann's last week from TennisIsMyLife (TML) and TennisData.app.

Used twice, by the same code:

- the one-time held-out evaluation (editions starting 1 June 2026 or later, complete before the 5 November 2026
  file snapshot), which unseals the provider rows with the frozen Phase 4 protocol; and
- a rehearsal on January to mid-May 2026, where the provider rows are open and Sackmann has the same matches, so the
  provider-built features can be compared with Sackmann-built ones without looking at any held-out outcome.

Rules (Phase 4 Data Audit, Part 3):

1. TML rows are the record. A TennisData.app row is added only if it matches no TML row (names in the date window,
   then validated ids), is not from one of the event families Sackmann omits, and is not the same pair in the same
   round within 3 days of a TML row.
2. Players: validated crosswalk, else a unique full-name (TML) or surname-and-initial (TennisData.app) match to a
   Sackmann player with tour-level matches since 2015, else a provider-only id.
3. An edition's tourney_date is TennisData.app's first main-draw day when the edition is in TennisData.app, else
   TML's earliest date. Best-of comes from the tournament. Ratings move only on completed matches.
"""
import datetime
from collections import Counter, defaultdict

from matchup_dna import tennisdata as td
from matchup_dna import tennisismylife as tml
from matchup_dna.crosswalk import (
    build_links, full_name_key, provider_name_key, sackmann_full_keys, sackmann_name_keys,
)
from matchup_dna.load import match_outcome, normalize_surface
from matchup_dna.merge import MAX_EDITION_GAP_DAYS, provider_only_id, tml_match
from matchup_dna.workload import to_day

NAME_HISTORY_START = 20150101


def ymd(day):
    return int(day.strftime("%Y%m%d"))


class NameResolver:
    """Unique name matches to Sackmann players who have tour-level matches since NAME_HISTORY_START."""

    def __init__(self, sackmann_matches, names):
        active = {(m["tour"], m[side]) for m in sackmann_matches if m["tourney_date"] >= NAME_HISTORY_START
                  for side in ("winner_id", "loser_id")}
        self.full, self.initial = defaultdict(set), defaultdict(set)
        for key in active:
            person = names.get(key)
            if person is None:
                continue
            for value in sackmann_full_keys(person["first"], person["last"]).values():
                self.full[(key[0], value)].add(key[1])
            for value in sackmann_name_keys(person["first"], person["last"]).values():
                self.initial[(key[0], value)].add(key[1])

    def by_full_name(self, tour, name):
        found = self.full.get((tour, full_name_key(name)), set())
        return next(iter(found)) if len(found) == 1 else None

    def by_initial(self, tour, name):
        key = provider_name_key(name)
        found = self.initial.get((tour, key), set()) if key else set()
        return next(iter(found)) if len(found) == 1 else None


def resolve_tml(tour, provider_id, name, links, resolver, report):
    if (tour, provider_id) in links:
        report["TML ids by crosswalk"] += 1
        return links[(tour, provider_id)]
    found = resolver.by_full_name(tour, name)
    if found is not None:
        report["TML ids by unique full name"] += 1
        return found
    report["TML ids new to Sackmann"] += 1
    return provider_only_id("tml", tour, provider_id)


def resolve_td(tour, provider_id, name, links, resolver, report):
    if (tour, provider_id) in links:
        report["TennisData.app ids by crosswalk"] += 1
        return links[(tour, provider_id)]
    found = resolver.by_initial(tour, name)
    if found is not None:
        report["TennisData.app ids by unique surname and initial"] += 1
        return found
    report["TennisData.app ids new to Sackmann"] += 1
    return provider_only_id("tennisdata", tour, provider_id)


def td_score(row):
    """A Sackmann-style score from the winner's side, the winner's side ("home" or "away"), and an outcome."""
    if row["status_extra"] == "WALKOVER":
        return "W/O", "home" if row["winner_code"] == "1" else "away"
    if row["status_extra"] not in ("FINISHED", "RETIRED") or row["winner_code"] not in ("1", "2"):
        return None, None
    winner = "home" if row["winner_code"] == "1" else "away"
    loser = "away" if winner == "home" else "home"
    sets = []
    for number in range(1, 6):
        won, lost = td.number(row[f"{winner}_set_{number}_score"]), td.number(row[f"{loser}_set_{number}_score"])
        if won is not None and lost is not None:
            sets.append(f"{int(won)}-{int(lost)}")
    if not sets:
        return None, None
    return " ".join(sets) + (" RET" if row["status_extra"] == "RETIRED" else ""), winner


def td_match(row, tourney_date, links, resolver, report):
    score, winner = td_score(row)
    if score is None:
        report["TennisData.app rows without a usable result (canceled, awarded, blank)"] += 1
        return None
    loser = "away" if winner == "home" else "home"
    tour = row["tour"]
    match = {
        "tour": tour, "key": (tour, f"TD-{td.edition_name(row['tournament'])}-{tourney_date}", row["match_id"],
                              td.ROUNDS.get(row["round"]) or "unknown"),
        "tourney_id": f"TD-{td.edition_name(row['tournament'])}-{tourney_date}", "tourney_name": row["tournament"],
        "tourney_level": "G" if td.is_grand_slam(row) else "A", "tourney_date": tourney_date,
        "match_num": row["match_id"], "surface": normalize_surface(row["surface"]),
        "round": td.ROUNDS.get(row["round"]) or "unknown", "best_of": td.best_of(row), "score": score,
        "outcome": match_outcome(score),
        "winner_id": resolve_td(tour, row[f"{winner}_id"], row[f"{winner}_name"], links, resolver, report),
        "winner_name": row[f"{winner}_name"], "winner_rank": None if td.number(row[f"{winner}_rank"]) is None else int(td.number(row[f"{winner}_rank"])),
        "loser_id": resolve_td(tour, row[f"{loser}_id"], row[f"{loser}_name"], links, resolver, report),
        "loser_name": row[f"{loser}_name"], "loser_rank": None if td.number(row[f"{loser}_rank"]) is None else int(td.number(row[f"{loser}_rank"])),
        "minutes": None, "draw_size": "", "winner_entry": "", "loser_entry": "", "source": "tennisdata",
        "w_ace": None, "w_svpt": None, "w_first_in": None, "l_ace": None, "l_svpt": None, "l_first_in": None,
        "stats": {prefix: {field: None for field in ("ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms",
                                                      "bpSaved", "bpFaced")} for prefix in ("w", "l")},
    }
    return match


def assemble(tml_rows, td_rows, sackmann_matches, names, tml_links, td_links, excluded_names, start, end, snapshot):
    """Provider matches for editions starting in [start, end) and finished before `snapshot`, under the rules in
    the module notes. Rows must be open (unsealed) for this window. Returns (matches, held-out keys, report)."""
    from matchup_dna.audit_tennisismylife import td_to_tml, td_to_tml_by_ids

    report = Counter()
    resolver = NameResolver(sackmann_matches, names)
    snapshot_date = ymd(snapshot)
    editions = tml.editions(tml_rows)
    tml_window = [r for r in tml_rows if start <= editions[(r["tour"], r["tourney_id"])]["start"] < end
                  and not editions[(r["tour"], r["tourney_id"])]["ongoing"]
                  and editions[(r["tour"], r["tourney_id"])]["end"] < snapshot_date]
    td_main = [r for r in td_rows if td.is_main_draw(r)]
    td_editions = td.editions(td_main)
    td_window = [r for r in td_main if start <= td_editions[td.row_key(r)]["tourney_date"] < end
                 and td_editions[td.row_key(r)]["last_day"] < snapshot
                 and r["tournament"] not in excluded_names]
    report["TML rows in the window"] = len(tml_window)
    report["TennisData.app main-draw rows in the window"] = len(td_window)

    direct = td_to_tml(td_window, tml_window)
    taken = {id(r["target"]) for r in direct if r["status"] == "linked"}
    second = td_to_tml_by_ids([r["item"] for r in direct if r["status"] != "linked"], tml_window, td_links, tml_links, taken)
    pair_of = {id(r["item"]): r["target"] for r in direct if r["status"] == "linked"}
    pair_of.update({id(row): target for row, target in second})
    report["TennisData.app rows matched to TML rows"] = len(pair_of)
    from matchup_dna.crosswalk import initial_keys
    for row in td_window:
        target = pair_of.get(id(row))
        if target is None or "winner_code" not in row or "winner_name" not in target:
            continue
        if row["winner_code"] in ("1", "2"):
            td_winner = provider_name_key(row["home_name" if row["winner_code"] == "1" else "away_name"])
            report["data check: TML and TennisData.app name the same winner"] += td_winner in initial_keys(target["winner_name"])
            report["data check: matched pairs with a winner in both"] += 1

    first_day = {}
    for row in td_window:
        target = pair_of.get(id(row))
        if target is not None:
            key = (target["tour"], target["tourney_id"])
            day = td_editions[td.row_key(row)]["first_day"]
            first_day[key] = min(day, first_day.get(key, day))

    matches, by_pair = [], defaultdict(list)
    for row in tml_window:
        key = (row["tour"], row["tourney_id"])
        date = ymd(first_day[key]) if key in first_day else editions[key]["start"]
        match = tml_match(row, {}, date)
        for side in ("winner", "loser"):
            match[f"{side}_id"] = resolve_tml(row["tour"], row[f"{side}_id"], row[f"{side}_name"], tml_links, resolver, report)
        matches.append(match)
        by_pair[(match["tour"], frozenset((match["winner_id"], match["loser_id"])), match["round"])].append(match)

    for row in td_window:
        if id(row) in pair_of:
            continue
        date = td_editions[td.row_key(row)]["tourney_date"]
        match = td_match(row, date, td_links, resolver, report)
        if match is None:
            continue
        near = [m for m in by_pair.get((match["tour"], frozenset((match["winner_id"], match["loser_id"])), match["round"]), ())
                if abs((to_day(m["tourney_date"]) - to_day(date)).days) <= MAX_EDITION_GAP_DAYS]
        if near:
            report["TennisData.app rows dropped as duplicates of TML rows by player ids"] += 1
            continue
        matches.append(match)
        report["TennisData.app rows added (no TML row)"] += 1
    keys = {m["key"] for m in matches}
    return matches, keys, dict(report)


def crosswalks(sackmann_overlap_matches, names):
    """The validated TML and TennisData.app crosswalks, rebuilt exactly as the audits build them (open rows only)."""
    from matchup_dna.audit_tennisdata import link_population
    from matchup_dna.audit_tennisismylife import to_sackmann

    tml_open = [r for r in tml.load_tml() if not r["sealed"]]
    pairs = []
    for result in to_sackmann(tml_open, sackmann_overlap_matches, names):
        if result["status"] != "linked":
            continue
        row, target = result["item"], result["target"]
        winner, loser = (target["winner_id"], target["loser_id"]) if result["same_order"] else (
            target["loser_id"], target["winner_id"])
        pairs += [(row["tour"], row["winner_id"], winner), (row["tour"], row["loser_id"], loser)]
    td_open = [r for r in td.load_provider() if not r["sealed"] and td.is_main_draw(r)]
    _, td_crosswalk, _ = link_population(td_open, sackmann_overlap_matches, names)
    return build_links(pairs)["links"], td_crosswalk["links"]


def excluded_tournaments(sackmann_overlap_matches, names):
    """TennisData.app tournament names whose open main-draw rows link to Sackmann less than half the time (the
    event families Sackmann omits). Names never seen in the open period are kept, as decided in the audit."""
    from matchup_dna.audit_tennisdata import ELIGIBLE_SHARE, link_population, tournament_mapping
    td_open = [r for r in td.load_provider() if not r["sealed"]]
    linked, _, by_ids = link_population([r for r in td_open if td.is_main_draw(r)], sackmann_overlap_matches, names)
    mapping = tournament_mapping(td_open, linked, by_ids)
    return sorted(name for (_, name), entry in mapping.items() if entry["share"] < ELIGIBLE_SHARE)


def snapshot_day():
    return datetime.date(2026, 11, 5)

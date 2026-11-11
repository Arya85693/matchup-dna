"""ITF extension, stage I2: every Sackmann singles match as one list, read through the seal.

Three file families, all used as rating history; only ITF main-draw singles are scored (itf_splits.in_scope):

    itf                     atp_matches_futures_YYYY.csv, wta_matches_qual_itf_YYYY.csv (the women's file also
                            holds WTA 125 events and tour and ITF qualifying)
    challenger_qualifying   atp_matches_qual_chall_YYYY.csv (Challenger main draws and tour qualifying)
    main                    atp_matches_YYYY.csv, wta_matches_YYYY.csv

Each match is matchup_dna.load.parse_match's dict plus:

    family, itf_scope   which family it came from; whether it is a scored ITF match
    tier                1-5, the field-strength tier of a scored match (None otherwise; see TIERS)
    stats               both serve lines, as workload.load_matches_with_workload stores them (from 2015 only)
    outcome_note        "unmarked retirement" when the outcome rule below changed the outcome

Only the fields later stages read are kept (KEPT); names only for scored matches.

Repeated rows: the women's ITF file repeats some rows exactly (all of 2014 Nanchang WTA 125 qualifying, for one). An
exact repeat of a row already read is dropped, so the match counts once, and LOAD_REPORT counts it. Two different
rows with the same key stop the load.

The key gains the family, so a match key is unique across files.

The outcome rule (I1 audit, section 2): from 2025, many ITF retirements are written as finished matches with a
partial score ("6-2 0-0"). A "completed" match whose winner did not win a majority of the sets is a retirement here,
so it neither moves the ratings nor counts as a rated match. Rows whose score cannot be parsed keep their outcome.
A set counts only when finished (6 games and a 2-game lead, 7-5, 7-6, or a match tiebreak to 10 by 2). The rule
applies to the ITF files only: the main-tour files hold short-set events (first to 4 games, such as the Next Gen
Finals) whose finished matches it would misread, and the audit found the defect in the ITF files alone.

Tiers (I1 audit, the 2024 renaming of the women's levels, matched by the median rank of first-round entrants):
men M15 = 1, M25 = 2; women W10/W15 = 1, W25/W35 = 2, W40/W50 = 3, W60/W75/W80 = 4, W100 = 5. Men's "S" events
(up to 2019) mixed both men's levels and get no tier; they are burn-in history and never scored.
"""
import hashlib
import re
from collections import Counter
from pathlib import Path

from matchup_dna import itf_splits
from matchup_dna.load import DATA_DIR, parse_match
from matchup_dna.serve_stats import stat_line
from matchup_dna.workload import parse_sets

FAMILIES = (
    ("itf", re.compile(r"(atp_matches_futures|wta_matches_qual_itf)_\d{4}\.csv")),
    ("challenger_qualifying", re.compile(r"atp_matches_qual_chall_\d{4}\.csv")),
    ("main", re.compile(r"(atp|wta)_matches_\d{4}\.csv")),
)
TIERS = {"ATP": {"15": 1, "25": 2},
         "WTA": {"10": 1, "15": 1, "25": 2, "35": 2, "40": 3, "50": 3, "60": 4, "75": 4, "80": 4, "100": 5}}
UNMARKED_RETIREMENT = "unmarked retirement"


def family_of(name):
    return next((family for family, pattern in FAMILIES if pattern.fullmatch(name)), None)


def files(data_dir=DATA_DIR):
    """[(tour, family, path)] for every match file the ITF work reads."""
    found = []
    for tour in ("ATP", "WTA"):
        for path in sorted((Path(data_dir) / tour.lower()).glob("*.csv")):
            family = family_of(path.name)
            if family:
                found.append((tour, family, path))
    return found


def sets_needed(best_of):
    return best_of // 2 + 1 if best_of in (3, 5) else None


def set_won_by_winner(winner_games, loser_games, kind):
    """A finished set the match winner took: 6 games with a 2-game lead, 7-5 or 7-6, or a match tiebreak to 10 by 2.
    An unfinished set ("3-0" when play stopped) is not won by anyone."""
    lead = winner_games - loser_games
    if kind == "match tiebreak":
        return winner_games >= 10 and lead >= 2
    return (winner_games >= 6 and lead >= 2) or (winner_games == 7 and loser_games in (5, 6))


def apply_outcome_rule(match):
    """Marks a "completed" match whose winner did not win a majority of sets as retired (see the module notes)."""
    if match["outcome"] != "completed":
        return match
    needed, sets = sets_needed(match["best_of"]), parse_sets(match["score"])
    if needed is None or not sets:
        return match
    won = sum(set_won_by_winner(w, l, kind) for w, l, kind in sets)
    if won < needed:
        match["outcome"] = "retired"
        match["outcome_note"] = UNMARKED_RETIREMENT
    return match


LOAD_REPORT = {"exact_repeats": Counter()}   # the last load's dropped repeats, by (tour, family, scored)
HISTORY_FROM = 20100101     # ratings warm up for 11 years before development begins
STATS_FROM = 20150101       # serve lines older than this weigh under 2% at a 52-week half-life, so they are dropped
KEPT = ("tour", "key", "tourney_id", "tourney_level", "tourney_date", "surface", "round", "best_of", "outcome",
        "winner_id", "loser_id", "winner_rank", "loser_rank")


def to_match(row, tour, family):
    """The fields the ratings, features and profiles read, and nothing else: the full history is about a million
    matches per tour, so each record is kept small."""
    parsed = parse_match(row, tour)
    if family == "itf":       # the main-tour files have short-set events (first to 4 games) and no such defect
        parsed = apply_outcome_rule(parsed)
    match = {field: parsed[field] for field in KEPT}
    match["key"] = parsed["key"] + (family,)
    match["family"] = family
    match["itf_scope"] = family == "itf" and itf_splits.in_scope(row, tour)
    match["tier"] = TIERS[tour].get(match["tourney_level"].strip()) if match["itf_scope"] else None
    match["outcome_note"] = parsed.get("outcome_note")
    if match["itf_scope"]:
        match["winner_name"], match["loser_name"] = parsed["winner_name"], parsed["loser_name"]
    else:
        match["winner_name"] = match["loser_name"] = ""
    if match["tourney_date"] >= STATS_FROM and (row["w_svpt"].strip() or row["l_svpt"].strip()):
        match["stats"] = {prefix: stat_line(row, prefix) for prefix in ("w", "l")}
    return match


def load(data_dir=DATA_DIR, allow_held_out=None, families=None, tours=("ATP", "WTA"), since=HISTORY_FROM):
    """Every match from the three families dated `since` or later, through the seal (itf_splits.rows).
    `allow_held_out` None means: only if the frozen ITF protocol is committed. A held-out-period row in the result
    when the seal is on is a defect, so the load stops."""
    matches, seen = [], {}
    LOAD_REPORT["exact_repeats"] = Counter()
    for tour, family, path in files(data_dir):
        if (families and family not in families) or tour not in tours:
            continue
        for row in itf_splits.rows(path, allow_held_out=allow_held_out):
            if since is not None and int(row["tourney_date"]) < since:
                continue
            match = to_match(row, tour, family)
            content = hashlib.blake2b("\x1f".join(row.values()).encode("utf-8"), digest_size=16).digest()
            if match["key"] in seen:
                if seen[match["key"]] != content:
                    raise SystemExit(f"two different rows share the key {match['key']}")
                LOAD_REPORT["exact_repeats"][(tour, family, match["itf_scope"])] += 1
                continue
            seen[match["key"]] = content
            matches.append(match)
    if allow_held_out is False and any(m["tourney_date"] >= itf_splits.HELD_OUT_START for m in matches):
        raise SystemExit("the seal failed: a held-out-period row was read")
    return matches


def scope_matches(matches, split=None):
    """The scored ITF matches, optionally of one split."""
    return [m for m in matches if m["itf_scope"] and (split is None or itf_splits.split_of(m["tourney_date"]) == split)]

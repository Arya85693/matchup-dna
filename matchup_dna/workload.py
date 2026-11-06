"""Physical workload of one match, and recent workload before a tournament starts.

These are proxies for physical load, not measurements of fatigue. For one match both players share:

    minutes   time on court, Sackmann's `minutes`
    points    total points played, w_svpt + l_svpt (every point is one player's service point)
    games     games played, from the score; a set's games are both players' games in it, a match tiebreak
              ("[10-8]") counts as one game
    sets      sets started, from the score, including the unfinished set of a retirement

Rules (each documented in the Phase 4 Data Audit addendum):

- A walkover is a genuine zero: no court time. It is never imputed and never counted as a match played.
- A completed match uses its full record. A retirement or default uses what was played (partial workload),
  and is marked "partial". A retirement with no games recorded is unknown.
- Abandoned matches and unknown scores are unknown.
- A blank value is missing, never zero. A value that breaks a plausibility rule is set to missing and counted.

This module reads Sackmann's files itself and leaves matchup_dna.load unchanged.
"""
import bisect
import csv
import datetime
import re
from collections import defaultdict

from matchup_dna.load import DATA_DIR, TOURS, match_files, parse_match, to_int
from matchup_dna.serve_stats import stat_line

SET_SCORE = re.compile(r"^(\d+)-(\d+)(?:\(\d+\))?$")
MATCH_TIEBREAK = re.compile(r"^\[(\d+)-(\d+)\]$")
ENDING_MARKERS = ("RET", "W/O", "WALKOVER", "DEF", "DEF.", "DEFAULT", "ABD", "AB", "ABANDONED", "UNFINISHED",
                  "PLAYED", "AND")

# Plausibility rules. Every game needs at least 4 points, so points below 4 per game are impossible. Minutes are
# checked per game: the 2010-2020 distribution and the cut-offs are in the audit addendum.
MIN_POINTS_PER_GAME = 4.0
MAX_POINTS_PER_GAME = 20.0
MIN_MINUTES_PER_GAME = 1.5
MAX_MINUTES_PER_GAME = 15.0

RECENT_WINDOW_DAYS = 14


def load_matches_with_workload(tours=TOURS, data_dir=DATA_DIR):
    """Sackmann matches as matchup_dna.load builds them, plus minutes, draw size, entry codes, and both players'
    full statistic lines under "stats" ({"w": line, "l": line}, see serve_stats.stat_line)."""
    matches = []
    for tour in tours:
        for path in match_files(tour, data_dir):
            with open(path, encoding="utf-8", newline="") as file:
                for row in csv.DictReader(file):
                    match = parse_match(row, tour)
                    match["minutes"] = to_int(row["minutes"])
                    match["draw_size"] = row["draw_size"].strip()
                    match["winner_entry"] = row["winner_entry"].strip().upper()
                    match["loser_entry"] = row["loser_entry"].strip().upper()
                    match["stats"] = {prefix: stat_line(row, prefix) for prefix in ("w", "l")}
                    match["source"] = "sackmann"
                    matches.append(match)
    return matches


def parse_sets(score):
    """[(winner games, loser games, kind)] for each set in a score written from the winner's side, with kind
    "set" or "match tiebreak". Returns None if any token is not a set, a match tiebreak, or an ending marker."""
    sets = []
    for token in score.split():
        upper = token.upper()
        if upper in ENDING_MARKERS or upper.startswith("RET") or upper.startswith("DEF"):
            continue
        found = SET_SCORE.match(token)
        if found:
            sets.append((int(found.group(1)), int(found.group(2)), "set"))
            continue
        found = MATCH_TIEBREAK.match(token)
        if found:
            sets.append((int(found.group(1)), int(found.group(2)), "match tiebreak"))
            continue
        return None
    return sets


def games_in(sets):
    """(winner games, loser games) over all sets; a match tiebreak is one game to its winner."""
    won = lost = 0
    for a, b, kind in sets:
        if kind == "match tiebreak":
            won, lost = (won + 1, lost) if a > b else (won, lost + 1)
        else:
            won, lost = won + a, lost + b
    return won, lost


def match_workload(match):
    """{"kind", "minutes", "points", "games", "sets", "winner_games", "loser_games", "flags"} for one match.

    kind is "played" (completed), "partial" (retired or defaulted after play began), "walkover", or "unknown".
    Values are None when unknown. flags lists any value set to missing by a plausibility rule.
    """
    empty = {"minutes": None, "points": None, "games": None, "sets": None, "winner_games": None,
             "loser_games": None, "flags": []}
    outcome = match["outcome"]
    if outcome == "walkover":
        return dict(empty, kind="walkover", minutes=0, points=0, games=0, sets=0, winner_games=0, loser_games=0)
    if outcome not in ("completed", "retired", "default"):
        return dict(empty, kind="unknown")
    sets = parse_sets(match["score"])
    if not sets:
        return dict(empty, kind="unknown")
    kind = "played" if outcome == "completed" else "partial"
    winner_games, loser_games = games_in(sets)
    games = winner_games + loser_games
    result = dict(empty, kind=kind, games=games, sets=len(sets), winner_games=winner_games, loser_games=loser_games,
                  flags=[])

    w, l = match.get("w_svpt"), match.get("l_svpt")
    if w is not None and l is not None and w > 0 and l > 0:
        points = w + l
        if games and not MIN_POINTS_PER_GAME <= points / games <= MAX_POINTS_PER_GAME:
            result["flags"].append("implausible points")
        else:
            result["points"] = points
    minutes = match.get("minutes")
    if minutes is not None:
        if minutes <= 0 or (games and not MIN_MINUTES_PER_GAME <= minutes / games <= MAX_MINUTES_PER_GAME):
            result["flags"].append("implausible minutes")
        else:
            result["minutes"] = minutes
    return result


def to_day(date):
    return datetime.date(date // 10000, date // 100 % 100, date % 100)


def recent_workload(matches, targets, window_days=RECENT_WINDOW_DAYS):
    """Tournament-start workload: for each target match and side, the player's games, points, and minutes over
    matches dated in the `window_days` days before the target's tourney_date (strictly earlier dates only, the
    Phase 3 point-in-time rule), and the number of those matches.

    A sum is None when any match in the window has that measure unknown. No matches in the window is a genuine
    zero. Walkovers add nothing. Returns {(match key, "winner" or "loser"): values}.
    """
    by_player = defaultdict(list)
    for match in matches:
        if match["winner_id"] == match["loser_id"]:
            continue
        load = match_workload(match)
        if load["kind"] == "walkover":
            continue
        for side in ("winner", "loser"):
            by_player[(match["tour"], match[f"{side}_id"])].append((to_day(match["tourney_date"]).toordinal(), load))
    days = {}
    for player, history in by_player.items():
        history.sort(key=lambda item: item[0])
        days[player] = [day for day, _ in history]

    found = {}
    for match in targets:
        start = to_day(match["tourney_date"]).toordinal()
        for side in ("winner", "loser"):
            player = (match["tour"], match[f"{side}_id"])
            history = by_player.get(player, ())
            low = bisect.bisect_left(days.get(player, ()), start - window_days)
            high = bisect.bisect_left(days.get(player, ()), start)
            window = [load for _, load in history[low:high]]
            values = {"matches": len(window)}
            for measure in ("games", "points", "minutes"):
                known = [load[measure] for load in window]
                values[measure] = None if any(v is None for v in known) else sum(known)
            found[(match["key"], side)] = values
    return found

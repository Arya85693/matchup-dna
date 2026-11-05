"""Round-aware information: what is known before a match from strictly earlier rounds of the same tournament.

Phase 3 freezes every feature at the start of a tournament week. A round-aware prediction may also use the
tournament's earlier rounds, because a knockout round is played only after the previous round has finished.
That is a different information set, so these features form a separate research track with its own baseline.

Chronology rules (an edition is one tour + tourney_id):

- Knockout rounds are ordered R128 < R64 < R32 < R16 < QF < SF < F. A round-robin stage ("RR") is complete before
  the knockout rounds of the same edition. A player's earlier matches are those in strictly earlier rounds.
- Matches in the same round are never ordered against each other, and no rest days are inferred.
- A round-robin match gets no round-aware features: the order of round-robin matches is unknown.
- Davis Cup and Billie Jean King Cup ties (level D), and editions with any other round label (for example the
  Olympic bronze-medal match), are left out: their order cannot be established.
- A player's record in the edition must be complete: every round from their first match to the round before the
  target is present. A first match one round after the edition's first round is accepted as a bye only when the
  edition has byes: its first round has fewer than twice as many matches as its second round. (Sackmann's
  draw_size cannot be used for this: from 2016 it records 28-player draws as 32, and 56 and 96 as 64 and 128.)
  Anything else is a gap, and the match is not eligible. A first-round record missing from the data would look
  like a bye; in Sackmann's main draws that is rare, and it would understate one match of workload.
- An edition where a player appears twice in one knockout round, or plays on after losing, is not eligible.

Round-aware Elo. The canonical ratings (matchup_dna.elo.run_elo) are read, never changed. For each edition, a
temporary copy of every player's start-of-week rating is updated round by round with the same K and the same
"completed best-of-3 or best-of-5 only" rule. Matches in one round are applied together, like Phase 2's week.
The copy is discarded after the edition, so each match moves the canonical ratings once, exactly as before.
"""
import bisect
import math
from collections import defaultdict

from matchup_dna.elo import ELO_K, SURFACE_ELO_K, SURFACE_WEIGHT, START_RATING, expected_score, is_rated, k_factor
from matchup_dna.workload import match_workload

KNOCKOUT = {"R128": 1, "R64": 2, "R32": 3, "R16": 4, "QF": 5, "SF": 6, "F": 7}
ROUND_ROBIN = "RR"
EXCLUDED_LEVELS = ("D",)
LN10_OVER_400 = math.log(10) / 400
UNRELIABLE_PLAYED = 20


def round_order(round_name):
    """0 for the round-robin stage, 1-7 for knockout rounds, None for anything else."""
    if round_name == ROUND_ROBIN:
        return 0
    return KNOCKOUT.get(round_name)


def has_byes(members):
    """True when the edition's first knockout round has fewer than twice as many matches as its second round,
    so some players started in the second round."""
    counts = defaultdict(int)
    for match in members:
        order = round_order(match["round"])
        if order:
            counts[order] += 1
    if not counts:
        return False
    first = min(counts)
    return counts[first] < 2 * counts.get(first + 1, 0)


class StartRatings:
    """Each player's canonical rating at the start of any week, read from run_elo's output.

    Ratings change only through rated matches, which run_elo applies at the end of each week. So a player's
    rating at the start of week d equals the pre-week rating recorded at their first rated match in week d or
    later, or their final rating if they have none. `surface` selects the surface ratings of a surface-Elo run.
    """

    def __init__(self, predictions, ratings, surface=False):
        label = "surface_" if surface else ""
        history = defaultdict(list)
        for prediction in predictions:
            match = prediction["match"]
            if surface and match["surface"] is None:
                continue
            for side in ("winner", "loser"):
                key = (match["tour"], match[f"{side}_id"]) + ((match["surface"],) if surface else ())
                history[key].append((match["tourney_date"], prediction[f"{side}_{label}rating"],
                                     prediction[f"{side}_{label}played"]))
        self.history = {}
        for key, items in history.items():
            items.sort(key=lambda item: item[0])
            self.history[key] = ([date for date, _, _ in items], items)
        self.ratings = ratings

    def at(self, key, date):
        """(rating, rated matches played) at the start of week `date` for a ratings key."""
        dates, items = self.history.get(key, ((), ()))
        index = bisect.bisect_left(dates, date)
        if index < len(items):
            return items[index][1], items[index][2]
        final = self.ratings.get(key)
        return (final["rating"], final["played"]) if final else (START_RATING, 0)


def edition_problem(members):
    """Why an edition's matches cannot be ordered, or None if they can."""
    if any(match["tourney_level"] in EXCLUDED_LEVELS for match in members):
        return "team event"
    if any(round_order(match["round"]) is None for match in members):
        return "unordered round"
    seen, lost_in = set(), {}
    for match in members:
        order = round_order(match["round"])
        for side in ("winner", "loser"):
            player = match[f"{side}_id"]
            if order > 0:
                if (player, order) in seen:
                    return "player twice in one round"
                seen.add((player, order))
            if side == "loser" and order > 0:
                lost_in[player] = min(order, lost_in.get(player, order))
    for player, order in seen:
        if player in lost_in and order > lost_in[player]:
            return "player continues after losing"
    return None


def chronology(player, target_order, matches_of, first_round, has_byes):
    """"ok" if the player's record before the target round is complete, else the reason it is not."""
    earlier = sorted(round_order(m["round"]) for m in matches_of if 0 < round_order(m["round"]) < target_order)
    start = earlier[0] if earlier else target_order
    if earlier != list(range(start, target_order)):
        return "gap in earlier rounds"
    if start == first_round or (start == first_round + 1 and has_byes):
        return "ok"
    return "first round missing"


def player_history(player, earlier, starts, week):
    """Workload, dominance, and route values for one player from their earlier matches in the edition."""
    values = {"matches": 0, "walkovers": 0, "partial": 0, "games": 0, "points": 0, "minutes": 0, "sets": 0,
              "games_won": 0, "games_lost": 0, "faced": 0, "unreliable_faced": 0, "relative_elo_sum": 0.0,
              "max_opponent_elo": None}
    own_rating = starts.at((earlier[0]["tour"], player), week)[0] if earlier else None
    for match in earlier:
        load = match_workload(match)
        side = "winner" if match["winner_id"] == player else "loser"
        opponent = match["loser_id"] if side == "winner" else match["winner_id"]
        if load["kind"] == "walkover":
            values["walkovers"] += 1
            continue
        if load["kind"] == "unknown":
            for measure in ("games", "points", "minutes", "sets"):
                values[measure] = None
            values["matches"] += 1
            continue
        values["matches"] += 1
        values["partial"] += load["kind"] == "partial"
        for measure in ("games", "points", "minutes", "sets"):
            values[measure] = None if values[measure] is None or load[measure] is None else values[measure] + load[measure]
        won, lost = (load["winner_games"], load["loser_games"]) if side == "winner" else (
            load["loser_games"], load["winner_games"])
        values["games_won"] += won
        values["games_lost"] += lost
        opponent_rating, opponent_played = starts.at((match["tour"], opponent), week)
        values["faced"] += 1
        values["unreliable_faced"] += opponent_played < UNRELIABLE_PLAYED
        values["relative_elo_sum"] += opponent_rating - own_rating
        values["max_opponent_elo"] = max(opponent_rating, values["max_opponent_elo"] or opponent_rating)
    total = values["games_won"] + values["games_lost"]
    values["games_won_share"] = values["games_won"] / total if total else None
    values["route_relative_elo"] = values["relative_elo_sum"] / values["faced"] if values["faced"] else None
    return values


def shadow_shifts(members, starts, surface_starts, overall_rule=ELO_K, surface_rule=SURFACE_ELO_K):
    """{(match key, side): (overall Elo shift, blended surface-Elo shift)} before each match in the edition.

    A shift is the temporary rating minus the start-of-week rating, from rated matches in strictly earlier
    stages of the edition. Nothing here is written back to the canonical ratings.
    """
    week = members[0]["tourney_date"]
    tour = members[0]["tour"]
    surface = members[0]["surface"]
    stages = sorted({round_order(m["round"]) for m in members})
    elo, elo48, surf48, played = {}, {}, {}, defaultdict(int)

    def state(table, key, source):
        if key not in table:
            table[key] = source.at(key, week)
        return table[key]

    shifts = {}
    for stage in stages:
        in_stage = [m for m in members if round_order(m["round"]) == stage]
        for match in in_stage:
            for side in ("winner", "loser"):
                player = match[f"{side}_id"]
                base = starts.at((tour, player), week)[0]
                base48 = surface_starts["overall"].at((tour, player), week)[0]
                overall_shift = state(elo, player, _Bound(starts, tour))[0] - base
                shift48 = state(elo48, player, _Bound(surface_starts["overall"], tour))[0] - base48
                if surface is not None:
                    base_surface = surface_starts["surface"].at((tour, player, surface), week)[0]
                    surface_shift = state(surf48, player, _Bound(surface_starts["surface"], tour, surface))[0] - base_surface
                    blended = (1 - SURFACE_WEIGHT) * shift48 + SURFACE_WEIGHT * surface_shift
                else:
                    blended = shift48
                shifts[(match["key"], side)] = (overall_shift, blended)
        changes = defaultdict(float)
        for match in in_stage:
            if not is_rated(match):
                continue
            winner, loser = match["winner_id"], match["loser_id"]
            tables = [("elo", elo, _Bound(starts, tour), overall_rule),
                      ("elo48", elo48, _Bound(surface_starts["overall"], tour), surface_rule)]
            if surface is not None:
                tables.append(("surf48", surf48, _Bound(surface_starts["surface"], tour, surface), surface_rule))
            for name, table, source, rule in tables:
                w_rating, w_played = state(table, winner, source)
                l_rating, l_played = state(table, loser, source)
                expected = expected_score(w_rating, l_rating)
                changes[(name, winner)] += k_factor(rule, w_played + played[(name, winner)]) * (1 - expected)
                changes[(name, loser)] -= k_factor(rule, l_played + played[(name, loser)]) * (1 - expected)
        for (name, player), change in changes.items():
            table = {"elo": elo, "elo48": elo48, "surf48": surf48}[name]
            rating, count = table[player]
            table[player] = (rating + change, count)
            played[(name, player)] += 1
    return shifts


class _Bound:
    """Adapts StartRatings.at to a per-player lookup for one tour (and surface)."""

    def __init__(self, ratings, tour, surface=None):
        self.ratings, self.tour, self.surface = ratings, tour, surface

    def at(self, player, week):
        key = (self.tour, player) + ((self.surface,) if self.surface else ())
        return self.ratings.at(key, week)


def round_aware_features(matches, elo_run, surface_run):
    """Round-aware values for every rated match.

    elo_run and surface_run are the (predictions, ratings) results of run_elo with ELO_K and SURFACE_ELO_K.
    Returns {match key: {"eligible": bool, "reason": str or None, "winner": values, "loser": values}}, where
    values hold the player's earlier-round workload, dominance, route difficulty, round-aware Elo shifts, and
    chronology status. Only strictly earlier rounds of the same edition are used.
    """
    starts = StartRatings(*elo_run)
    surface_starts = {"overall": StartRatings(*surface_run), "surface": StartRatings(*surface_run, surface=True)}
    editions = defaultdict(list)
    for match in matches:
        if match["winner_id"] != match["loser_id"]:
            editions[(match["tour"], match["tourney_id"])].append(match)

    found = {}
    for members in editions.values():
        targets = [m for m in members if is_rated(m)]
        if not targets:
            continue
        problem = edition_problem(members)
        if problem is None and len({m["tourney_date"] for m in members}) > 1:
            problem = "edition spans several dates"
        if problem:
            for match in targets:
                found[match["key"]] = {"eligible": False, "reason": problem, "winner": None, "loser": None}
            continue
        week = members[0]["tourney_date"]
        knockout_rounds = [round_order(m["round"]) for m in members if round_order(m["round"]) > 0]
        first_round = min(knockout_rounds) if knockout_rounds else None
        byes = has_byes(members)
        by_player = defaultdict(list)
        for match in members:
            for side in ("winner", "loser"):
                by_player[match[f"{side}_id"]].append(match)
        shifts = shadow_shifts(members, starts, surface_starts)
        for match in targets:
            order = round_order(match["round"])
            if order == 0:
                found[match["key"]] = {"eligible": False, "reason": "round-robin match", "winner": None, "loser": None}
                continue
            entry = {"eligible": True, "reason": None}
            for side in ("winner", "loser"):
                player = match[f"{side}_id"]
                status = chronology(player, order, by_player[player], first_round, byes)
                earlier = [m for m in by_player[player] if round_order(m["round"]) < order]
                values = player_history(player, earlier, starts, week)
                values["chronology"] = status
                values["elo_shift"], values["surface_elo_shift"] = shifts[(match["key"], side)]
                values["entry"] = match.get(f"{side}_entry", "")
                entry[side] = values
                if status != "ok":
                    entry.update(eligible=False, reason=status)
            found[match["key"]] = entry
    return found


def differences(a, b):
    """The pre-registered round-aware matchup features for player A against player B, each A minus B.

    Swapping A and B negates every value. Inputs are the per-player values from round_aware_features.
    """
    def log_games(values):
        return None if values["games"] is None else math.log1p(values["games"])

    def dominance(values):
        return 0.0 if values["games_won_share"] is None else values["games_won_share"] - 0.5

    def route(values):
        return 0.0 if values["route_relative_elo"] is None else values["route_relative_elo"] * LN10_OVER_400

    games_a, games_b = log_games(a), log_games(b)
    return {
        "ra_elo_shift_logit": (a["elo_shift"] - b["elo_shift"]) * LN10_OVER_400,
        "ra_surface_elo_shift_logit": (a["surface_elo_shift"] - b["surface_elo_shift"]) * LN10_OVER_400,
        "ra_dominance_diff": dominance(a) - dominance(b),
        "ra_log_games_diff": None if games_a is None or games_b is None else games_a - games_b,
        "ra_route_relative_elo_diff": route(a) - route(b),
    }

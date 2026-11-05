from matchup_dna.load import SURFACES

UNFINISHED = ("retired", "walkover", "default", "abandoned", "unknown")

# Outcomes whose serve totals come from points actually played.
SERVE_OUTCOMES = ("completed", "retired")


def player_matches(matches, player_key, before):
    """Matches the player played in tournament weeks strictly before `before` (YYYYMMDD).

    Same-week matches stay out because tourney_date is the Monday of the week, not the day played.
    Returns a list of (match, won) in date order.
    """
    tour, player_id = player_key
    used = []
    for match in matches:
        if match["tour"] != tour or match["tourney_date"] >= before:
            continue
        if match["winner_id"] == match["loser_id"]:
            continue
        if match["winner_id"] == player_id:
            used.append((match, True))
        elif match["loser_id"] == player_id:
            used.append((match, False))
    used.sort(key=lambda pair: pair[0]["tourney_date"])
    return used


def rate(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / denominator


def player_record(matches, player_key, before):
    used = player_matches(matches, player_key, before)

    record = {
        "matches": len(used),
        "wins": 0,
        "losses": 0,
        "surfaces": {surface: {"wins": 0, "losses": 0} for surface in SURFACES.values()},
        "unfinished": {outcome: {"wins": 0, "losses": 0} for outcome in UNFINISHED},
        "best_of_1": {"wins": 0, "losses": 0},
        "last_rank": None,
        "last_rank_date": None,
    }
    aces = first_in = ace_points = first_in_points = 0

    for match, won in used:
        side = "w" if won else "l"
        result = "wins" if won else "losses"

        if match["best_of"] == 1:
            record["best_of_1"][result] += 1
        elif match["outcome"] == "completed":
            record[result] += 1
            if match["surface"] is not None:
                record["surfaces"][match["surface"]][result] += 1
        else:
            record["unfinished"][match["outcome"]][result] += 1

        if match["outcome"] in SERVE_OUTCOMES:
            serve_points = match[f"{side}_svpt"]
            if serve_points:
                if match[f"{side}_ace"] is not None:
                    aces += match[f"{side}_ace"]
                    ace_points += serve_points
                if match[f"{side}_first_in"] is not None:
                    first_in += match[f"{side}_first_in"]
                    first_in_points += serve_points

        rank = match["winner_rank"] if won else match["loser_rank"]
        if rank is not None:
            record["last_rank"] = rank
            record["last_rank_date"] = match["tourney_date"]

    record["ace_rate"] = rate(aces, ace_points)
    record["first_serve_in"] = rate(first_in, first_in_points)
    record["serve_points"] = first_in_points
    return record

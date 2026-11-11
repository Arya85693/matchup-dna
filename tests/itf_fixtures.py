"""Synthetic match histories for the ITF extension tests (not a test module itself)."""
import random

from matchup_dna.serve_stats import STAT_FIELDS

SURFACES = ("Hard", "Clay", None)
WEEKS = [20190107 + 7 * i for i in range(0, 20)]      # tourney_date values are compared as numbers only


def week_dates(start=2019, years=3):
    """Mondays as YYYYMMDD integers, about one a fortnight, valid calendar dates."""
    import datetime
    day = datetime.date(start, 1, 7)
    found = []
    while day.year < start + years:
        found.append(int(day.strftime("%Y%m%d")))
        day += datetime.timedelta(days=14)
    return found


def stat_line(rng):
    svpt = rng.randint(50, 90)
    first_in = rng.randint(int(svpt * 0.5), int(svpt * 0.7))
    first_won = rng.randint(int(first_in * 0.6), first_in)
    second_won = rng.randint(0, svpt - first_in)
    line = {"svpt": svpt, "1stIn": first_in, "1stWon": first_won, "2ndWon": second_won, "SvGms": 10,
            "ace": rng.randint(0, 8), "df": rng.randint(0, 5), "bpFaced": rng.randint(2, 8)}
    line["bpSaved"] = rng.randint(0, line["bpFaced"])
    return {field: line[field] for field in STAT_FIELDS}


def matches(seed=7, players=14, per_week=8, dates=None, families=("itf", "main", "challenger_qualifying"),
            with_stats=True, tour="ATP"):
    """Matches in the itf_data record shape, every week mixing families, surfaces and outcomes."""
    rng = random.Random(seed)
    found = []
    for date in dates or week_dates():
        for n in range(per_week):
            winner, loser = rng.sample(range(1, players + 1), 2)
            family = families[n % len(families)]
            outcome = rng.choices(("completed", "retired", "walkover"), (0.9, 0.07, 0.03))[0]
            match = {"tour": tour, "key": (tour, f"T{date}", str(n), "R32", family), "tourney_id": f"T{date}",
                     "tourney_level": "15" if family == "itf" else ("G" if n == 1 else "A"),
                     "tourney_date": date, "surface": SURFACES[n % 3], "round": "R32", "best_of": 3,
                     "outcome": outcome, "winner_id": winner, "loser_id": loser,
                     "winner_rank": rng.choice((None, rng.randint(1, 2500))),
                     "loser_rank": rng.choice((None, rng.randint(1, 2500))),
                     "family": family, "itf_scope": family == "itf", "tier": 1 if family == "itf" else None,
                     "outcome_note": None, "winner_name": f"P{winner}", "loser_name": f"P{loser}"}
            if with_stats and outcome == "completed":
                match["stats"] = {"w": stat_line(rng), "l": stat_line(rng)}
            found.append(match)
    return found

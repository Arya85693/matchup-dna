import argparse

from matchup_dna.load import SURFACES, TOURS, load_matches, load_players
from matchup_dna.stats import UNFINISHED, player_matches, player_record


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare two players using only matches from tournament weeks before a date."
    )
    parser.add_argument("tour1", choices=TOURS, type=str.upper)
    parser.add_argument("id1", type=int)
    parser.add_argument("tour2", choices=TOURS, type=str.upper)
    parser.add_argument("id2", type=int)
    parser.add_argument("before", type=int, help="date as YYYYMMDD, usually a tournament Monday")
    parser.add_argument(
        "--list",
        dest="list_surface",
        metavar="SURFACE",
        help="also list each player's completed matches on this surface (Hard, Clay, Grass, Carpet, or All)",
    )
    return parser.parse_args()


def format_date(yyyymmdd):
    text = str(yyyymmdd)
    return f"{text[:4]}-{text[4:6]}-{text[6:]}"


def win_loss(counts):
    return f"{counts['wins']}-{counts['losses']}"


def percent(value):
    return "n/a" if value is None else f"{value:.1%}"


def rows_for(record):
    played = record["wins"] + record["losses"]
    rows = [
        ("Completed W-L", win_loss(record)),
        ("Win rate", percent(record["wins"] / played if played else None)),
    ]
    for surface in SURFACES.values():
        rows.append((f"{surface} W-L", win_loss(record["surfaces"][surface])))
    for outcome in UNFINISHED:
        rows.append((f"{outcome.capitalize()} W-L", win_loss(record["unfinished"][outcome])))
    rows.append(("Best-of-1 W-L", win_loss(record["best_of_1"])))
    rows.append(("First serve in", percent(record["first_serve_in"])))
    rows.append(("Ace rate", percent(record["ace_rate"])))
    rows.append(("Serve points used", f"{record['serve_points']:,}"))
    if record["last_rank"] is None:
        rows.append(("Last rank", "n/a"))
    else:
        rows.append(("Last rank", f"{record['last_rank']} ({format_date(record['last_rank_date'])})"))
    return rows


def print_comparison(label1, record1, label2, record2, before):
    print(f"Records from tournament weeks before {format_date(before)}\n")
    print(f"{'':<20}{label1:<32}{label2}")
    for (name, value1), (_, value2) in zip(rows_for(record1), rows_for(record2)):
        print(f"{name:<20}{value1:<32}{value2}")


def print_match_list(label, used, surface):
    print(f"\n{label}: completed matches on {surface}")
    count = wins = 0
    for match, won in used:
        if match["outcome"] != "completed" or match["best_of"] == 1:
            continue
        if surface != "All" and match["surface"] != surface:
            continue
        count += 1
        wins += won
        result = "W" if won else "L"
        print(
            f"  {result} {format_date(match['tourney_date'])} {match['tourney_name']} {match['round']}: "
            f"{match['winner_name']} d. {match['loser_name']} {match['score']}"
        )
    print(f"  {count} matches, {wins} wins")


def main():
    args = parse_args()
    keys = [(args.tour1, args.id1), (args.tour2, args.id2)]
    tours = tuple(sorted({tour for tour, _ in keys}))

    players = load_players(tours)
    for key in keys:
        if key not in players:
            raise SystemExit(f"Unknown player: {key[0]} {key[1]}")
    matches = load_matches(tours)

    labels = [f"{players[key]['name']} ({key[0]} {key[1]})" for key in keys]
    records = [player_record(matches, key, args.before) for key in keys]
    print_comparison(labels[0], records[0], labels[1], records[1], args.before)

    if args.list_surface:
        surface = args.list_surface.capitalize()
        if surface != "All" and surface not in SURFACES.values():
            raise SystemExit(f"Unknown surface: {args.list_surface}")
        for label, key in zip(labels, keys):
            print_match_list(label, player_matches(matches, key, args.before), surface)


if __name__ == "__main__":
    main()

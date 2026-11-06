import argparse

from compare import format_date
from matchup_dna.elo import (
    ELO_K,
    SURFACE_ELO_K,
    SURFACE_WEIGHT,
    blended_rating,
    expected_score,
    player_ratings,
    run_elo,
)
from matchup_dna.load import SURFACES, TOURS, load_matches, load_players

def parse_args():
    parser = argparse.ArgumentParser(
        description="Elo ratings and win probability for two players, using only tournament weeks before a date."
    )
    parser.add_argument("tour1", choices=TOURS, type=str.upper)
    parser.add_argument("id1", type=int)
    parser.add_argument("tour2", choices=TOURS, type=str.upper)
    parser.add_argument("id2", type=int)
    parser.add_argument("before", type=int, help="date as YYYYMMDD, usually a tournament Monday")
    return parser.parse_args()

def rating_text(state):
    return f"{state['rating']:.0f} ({state['played']} matches)"

def main():
    args = parse_args()
    if args.tour1 != args.tour2:
        raise SystemExit("ATP and WTA are separate rating pools, so both players must be on the same tour.")
    keys = [(args.tour1, args.id1), (args.tour2, args.id2)]

    players = load_players((args.tour1,))
    for key in keys:
        if key not in players:
            raise SystemExit(f"Unknown player: {key[0]} {key[1]}")
    matches = load_matches((args.tour1,))

    _, elo_ratings = run_elo(matches, ELO_K, before=args.before)
    _, surface_ratings = run_elo(matches, SURFACE_ELO_K, before=args.before)
    elo = [player_ratings(elo_ratings, key) for key in keys]
    surface = [player_ratings(surface_ratings, key) for key in keys]
    labels = [f"{players[key]['name']} ({key[0]} {key[1]})" for key in keys]

    print(f"Ratings from tournament weeks before {format_date(args.before)}\n")
    print(f"{'':<24}{labels[0]:<34}{labels[1]}")
    print(f"{'Elo':<24}{rating_text(elo[0]['overall']):<34}{rating_text(elo[1]['overall'])}")
    print(f"{'Surface Elo overall':<24}{rating_text(surface[0]['overall']):<34}{rating_text(surface[1]['overall'])}")
    for name in SURFACES.values():
        print(f"{'Surface Elo ' + name:<24}{rating_text(surface[0]['surfaces'][name]):<34}{rating_text(surface[1]['surfaces'][name])}")

    print(f"\nProbability that {players[keys[0]]['name']} wins")
    print(f"   {'Elo':<20}{expected_score(elo[0]['overall']['rating'], elo[1]['overall']['rating']):.1%}")
    for name in SURFACES.values():
        first, second = (
            blended_rating(ratings["overall"]["rating"], ratings["surfaces"][name]["rating"], SURFACE_WEIGHT)
            for ratings in surface
        )
        print(f"   {'Surface Elo, ' + name:<20}{expected_score(first, second):.1%}")

if __name__ == "__main__":
    main()

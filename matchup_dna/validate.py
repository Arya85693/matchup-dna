from collections import Counter

from matchup_dna.load import load_matches, load_players

OUTCOMES = ("completed", "retired", "walkover", "default", "abandoned", "unknown")


def validate(matches, players):
    seen_keys = set()
    duplicate_keys = []
    missing_players = []
    same_player = []
    surfaces = Counter()
    outcomes = Counter()
    best_of = Counter()

    for match in matches:
        if match["key"] in seen_keys:
            duplicate_keys.append(match)
        seen_keys.add(match["key"])

        for side in ("winner_id", "loser_id"):
            if (match["tour"], match[side]) not in players:
                missing_players.append((match, side))

        if match["winner_id"] == match["loser_id"]:
            same_player.append(match)

        surfaces[match["surface"]] += 1
        outcomes[match["outcome"]] += 1
        best_of[match["best_of"]] += 1

    return {
        "matches": len(matches),
        "duplicate_keys": duplicate_keys,
        "missing_players": missing_players,
        "same_player": same_player,
        "surfaces": surfaces,
        "outcomes": outcomes,
        "best_of": best_of,
    }


def describe(match):
    return (
        f"{match['tour']} {match['tourney_date']} {match['tourney_name']} "
        f"{match['round']}: {match['winner_name']} d. {match['loser_name']} {match['score']}"
    )


def print_report(report):
    print(f"Matches checked: {report['matches']:,}")

    print(f"\nDuplicate match keys: {len(report['duplicate_keys'])}")
    for match in report["duplicate_keys"]:
        print("  ", describe(match))

    print(f"\nPlayer ids missing from the player file: {len(report['missing_players'])}")
    for match, side in report["missing_players"]:
        print("  ", side, describe(match))

    print(f"\nRows where winner id equals loser id: {len(report['same_player'])}")
    for match in report["same_player"]:
        print("  ", describe(match))

    print("\nSurfaces (after normalization):")
    for surface, count in report["surfaces"].most_common():
        print(f"   {surface or 'missing':<8} {count:>8,}")

    print("\nOutcomes:")
    for outcome in OUTCOMES:
        print(f"   {outcome:<10} {report['outcomes'][outcome]:>8,}")

    print("\nBest of:")
    for sets, count in sorted(report["best_of"].items()):
        print(f"   {sets:<3} {count:>8,}")


if __name__ == "__main__":
    print_report(validate(load_matches(), load_players()))

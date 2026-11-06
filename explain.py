"""Matchup report for two players, using only matches from tournament weeks before a date.

    python explain.py ATP 206173 ATP 104925 20260525 --surface Clay --best-of 5

Shows the Phase 3 and Phase 4 win probabilities, overall and surface strength, serving and returning profiles
with sample sizes and approximate intervals, the expected serve-return matchup, what pushed the Phase 4
probability up or down, and data warnings. Contributions are associations from past matches, not causes.
Takes about a minute (it replays the tour's history up to the date).
"""
import argparse

from compare import format_date
from matchup_dna.elo import expected_score
from matchup_dna.experiment import tour_rows
from matchup_dna.interpret import describe, explain
from matchup_dna.load import SURFACES, TOURS, load_players
from matchup_dna.matchup import SACKMANN_LAST_WEEK, History, expected_serve, matchup_row, profile_interval
from matchup_dna.model import LogisticModel
from matchup_dna.phase4_experiment import PROFILE_SETTINGS, load_selection
from matchup_dna.phase4_features import load_phase4
from matchup_dna.phase4_model import PHASE3_GROUPS, Phase4Logistic
from matchup_dna.workload import load_matches_with_workload

PHASE3_L2 = {"ATP": 1000.0, "WTA": 100.0}
FEW_MATCHES = 10


def parse_args():
    parser = argparse.ArgumentParser(description="Matchup report from tournament weeks before a date.")
    parser.add_argument("tour1", choices=TOURS, type=str.upper)
    parser.add_argument("id1", type=int)
    parser.add_argument("tour2", choices=TOURS, type=str.upper)
    parser.add_argument("id2", type=int)
    parser.add_argument("before", type=int, help="date as YYYYMMDD, usually a tournament Monday")
    parser.add_argument("--surface", default="Hard", choices=list(SURFACES.values()))
    parser.add_argument("--best-of", type=int, default=3, choices=(3, 5))
    return parser.parse_args()


def share(value):
    return "n/a" if value is None else f"{value:.1%}"


def main():
    args = parse_args()
    if args.tour1 != args.tour2:
        raise SystemExit("ATP and WTA are separate rating pools, so both players must be on the same tour.")
    tour = args.tour1
    players = load_players((tour,))
    for player in (args.id1, args.id2):
        if (tour, player) not in players:
            raise SystemExit(f"Unknown player: {tour} {player}")
    names = [players[(tour, p)]["name"] for p in (args.id1, args.id2)]

    history = History(load_matches_with_workload((tour,)), tour, args.before, PROFILE_SETTINGS)
    row, a, b, meetings = matchup_row(history, args.id1, args.id2, args.surface, args.best_of)

    fit_rows = tour_rows(load_phase4("train") + load_phase4("validation"), tour)
    selection = load_selection()
    phase3 = LogisticModel(PHASE3_GROUPS, PHASE3_L2[tour]).fit(fit_rows)
    phase4 = Phase4Logistic(selection["groups"], selection["l2"][tour], selection["representations"][tour]).fit(fit_rows)
    p3, p4 = float(phase3.predict([row])[0]), float(phase4.predict([row])[0])
    representation = selection["representations"][tour]
    serve_field, return_field = ("serve_adjusted", "return_adjusted") if representation == "adjusted" else ("serve", "return")

    print(f"Matchup report: {names[0]} vs {names[1]} ({tour}), {args.surface}, best of {args.best_of}")
    print(f"Information from tournament weeks before {format_date(args.before)}. Models fitted on 2010-2023.\n")
    print(f"Probability that {names[0]} wins")
    print(f"   Elo                        {row['elo_probability']:.1%}")
    print(f"   Surface Elo                {row['surface_elo_probability']:.1%}")
    print(f"   Phase 3 model              {p3:.1%}")
    print(f"   Phase 4 model              {p4:.1%}   (Phase 3 features + serving and returning strength)")

    print(f"\n{'':<34}{names[0]:<26}{names[1]}")
    for label, key, fmt in (("Elo (rated matches)", "elo", None), ("Surface Elo, blended", "surface_elo_blended", None)):
        print(f"{label:<34}{a[key]:<26.0f}{b[key]:.0f}")
    print(f"{'Rated matches':<34}{a['elo_matches']:<26}{b['elo_matches']}")
    rank = [f"{s['rank'][0]} ({format_date(s['rank'][1])})" if s["rank"] else "none" for s in (a, b)]
    print(f"{'Last rank (date)':<34}{rank[0]:<26}{rank[1]}")
    days = [f"{s['days_since']} days" if s["days_since"] is not None else "no earlier match" for s in (a, b)]
    print(f"{'Since last match':<34}{days[0]:<26}{days[1]}")
    print(f"{'Form (last 10 vs Elo)':<34}{a['form']:<+26.3f}{b['form']:+.3f}")

    per_match = history.means[tour]["serve"][1]
    print("\nServing and returning (shares of points; 90% intervals are approximate)")
    for label, field in (("Service points won", serve_field), ("Return points won", return_field)):
        cells = []
        for snap in (a, b):
            profile = snap["profile"]
            attempts = profile[f"{field.split('_')[0]}_attempts"]
            weight = history.engine.prior * history.means[tour][field.split("_")[0]][1]
            low, high = profile_interval(profile[field], attempts, weight)
            cells.append(f"{profile[field]:.1%} ({low:.1%}-{high:.1%})")
        print(f"{label + (' (opp.-adjusted)' if representation == 'adjusted' else ''):<34}{cells[0]:<26}{cells[1]}")
    for label, field in (("Serve on " + args.surface, "serve_surface"), ("Return on " + args.surface, "return_surface"),
                         ("Serve, last few months", "serve_recent"), ("Return, last few months", "return_recent"),
                         ("First serves in", "first_in"), ("First-serve points won", "first_won"),
                         ("Second-serve points won", "second_won"), ("Aces per service point", "ace"),
                         ("Double faults per service point", "df"), ("Break points saved", "bp_saved"),
                         ("Break points converted", "bp_converted")):
        print(f"{label:<34}{share(a['profile'][field]):<26}{share(b['profile'][field])}")
    history_size = [snap["profile"]["serve_attempts"] / per_match for snap in (a, b)]
    print(f"{'Statistics history (matches)':<34}{history_size[0]:<26.1f}{history_size[1]:.1f}")

    mu_serve = history.means[tour]["serve"][0]
    e_ab = expected_serve(history, a["profile"], b["profile"], representation)
    e_ba = expected_serve(history, b["profile"], a["profile"], representation)
    print(f"\nExpected matchup (Barnett-Clarke: own serve minus the opponent's return edge; tour average {mu_serve:.1%})")
    print(f"   {names[0]} serving against {names[1]}: {e_ab:.1%} of service points")
    print(f"   {names[1]} serving against {names[0]}: {e_ba:.1%} of service points")
    edge = (e_ab - mu_serve) - (e_ba - mu_serve)
    print(f"   Net serve-return edge: {edge * 100:+.1f} points toward {names[0] if edge > 0 else names[1]}")
    if meetings:
        print(f"   Head-to-head: {meetings} earlier meetings; results against Elo's expectation, shrunk: {row['h2h_a']:+.3f} for {names[0]}")

    terms, total = explain(phase4, row)
    print(f"\nWhat moved the Phase 4 probability (log-odds terms, adding up to {total:+.3f}; associations, not causes)")
    for line in describe(terms, p4, names[0], names[1]):
        print(f"   {line}")

    warnings = []
    if args.before > SACKMANN_LAST_WEEK + 7:
        warnings.append(f"The date is after Sackmann's last week ({format_date(SACKMANN_LAST_WEEK)}). Later matches "
                        "are not included: the June-October 2026 provider data stays sealed until the held-out test.")
    for name, snap, size in zip(names, (a, b), history_size):
        if size == 0:
            warnings.append(f"{name} has no serve statistics history: their serve and return are the tour average.")
        elif size < FEW_MATCHES:
            warnings.append(f"{name} has under {FEW_MATCHES} matches of statistics: their profile is mostly the tour average.")
        if snap["elo_matches"] < 20:
            warnings.append(f"{name} has {snap['elo_matches']} rated matches: Elo is unreliable.")
        if not snap["rank"]:
            warnings.append(f"{name} has no recorded rank.")
    warnings.append("Round-aware information (earlier rounds of the same event) is not used: this is a tournament-start "
                    "prediction.")
    print("\nData and uncertainty warnings")
    for warning in warnings:
        print(f"   - {warning}")


if __name__ == "__main__":
    main()

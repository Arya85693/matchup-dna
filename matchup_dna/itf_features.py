"""ITF extension, stage I2: pre-match feature rows for scored ITF matches.

A row is Phase 3's row (matchup_dna.features.feature_row, unchanged) built from an all-level Elo replay
(itf_ratings), plus:

    tier, tourney_id, split            the match's field-strength tier, edition and split
    a_/b_ serve, return, serve_adjusted, return_adjusted, serve_attempts
                                       Phase 4's point-in-time serve-return profiles (matchup_dna.profiles,
                                       unchanged), from every level's serve counts since 2015

Two pools:

    every_level   ITF, Challenger, qualifying and main-tour matches all move the ratings, rest, form and profiles
                  (models B0, B1, M1, M2)
    main_only     only main-tour matches do, as in the production main-tour model; ITF matches are predicted but
                  move nothing, and profiles use Phase 4's main-tour averages (baseline B2)

Profiles use Phase 4's settings (52-week half-life, 4 pseudo-matches, opponent-adjusted). In the every_level pool
the tour averages they shrink toward are ITF's own, from scored ITF matches in January-June 2025 (development).

Nothing here reads a result before the match it describes: ratings are start-of-week, history and profiles cover
earlier tourney_dates only, the Phase 3 rule. `player_history` and `profile_values` are copies of
features.player_history and profiles.replay that keep values only for the matches asked for (memory) and take a
`counts` rule for the main_only pool; with every match counting they give the same values (tests check this).
"""
from collections import defaultdict, deque

from matchup_dna import itf_ratings, itf_splits
from matchup_dna.elo import win_probability
from matchup_dna.features import FORM_MATCHES, PLAYED_OUTCOMES, feature_row, to_day
from matchup_dna.profiles import ProfileEngine, averages, match_observations, to_ordinal

ROWS_FROM = 20210101          # rows for development onward
HISTORY_FROM = 20190101       # rest and form: days since is capped at 365, form is the last 10 rated matches
PROFILE_HALF_LIFE, PROFILE_PRIOR = 52, 4
SERVE_MEAN_WINDOW = (20250101, 20250701)
PROFILE_KEEP = ("serve", "return", "serve_adjusted", "return_adjusted", "serve_attempts")
POOLS = ("every_level", "main_only")


def counts_rule(pool):
    if pool not in POOLS:
        raise ValueError(pool)
    return None if pool == "every_level" else (lambda match: match["family"] == "main")


def player_history(matches, elo_predictions, counts=None, want=None):
    """features.player_history with `counts` (matches that add rest and form; default all) and `want` (matches whose
    values are kept; default all)."""
    played = defaultdict(list)
    for match in matches:
        if (match["outcome"] in PLAYED_OUTCOMES and match["winner_id"] != match["loser_id"]
                and (counts is None or counts(match))):
            played[match["tourney_date"]].append(match)
    rated = defaultdict(list)
    for prediction in elo_predictions:
        rated[prediction["match"]["tourney_date"]].append(prediction)

    last_played = {}
    recent = defaultdict(lambda: deque(maxlen=FORM_MATCHES))
    history = {}
    for date in sorted(set(played) | set(rated)):
        for prediction in rated[date]:
            match = prediction["match"]
            if want is not None and not want(match):
                continue
            for side in ("winner", "loser"):
                player = (match["tour"], match[f"{side}_id"])
                last = last_played.get(player)
                days = None if last is None else (to_day(date) - to_day(last[0])).days
                form = recent.get(player)
                history[(match["key"], side)] = {
                    "days_since": days,
                    "form": sum(form) / len(form) if form else 0.0,
                    "form_matches": len(form) if form else 0,
                    "overlap": days is not None and days < (14 if last[1] == "G" else 7),
                }
        for match in played[date]:
            for side in ("winner", "loser"):
                last_played[(match["tour"], match[f"{side}_id"])] = (date, match["tourney_level"])
        for prediction in rated[date]:
            match = prediction["match"]
            if counts is not None and not counts(match):
                continue
            surprise = 1 - win_probability(prediction)
            recent[(match["tour"], match["winner_id"])].append(surprise)
            recent[(match["tour"], match["loser_id"])].append(-surprise)
    return history


def profile_values(matches, engine, want, counts=None, fields=PROFILE_KEEP):
    """profiles.replay's features, kept only for matches where want(match) and only `fields`; matches where
    counts(match) is false add no statistics. Returns {(match key, side): {field: value}}."""
    by_date = defaultdict(list)
    for match in matches:
        if match["winner_id"] != match["loser_id"]:
            by_date[match["tourney_date"]].append(match)
    found = {}
    for date in sorted(by_date):
        day = to_ordinal(date)
        pending = []
        for match in by_date[date]:
            observed = match_observations(match) if counts is None or counts(match) else {}
            keep = want(match)
            if not observed and not keep:
                continue            # player() changes nothing, so it is computed only when needed
            tour, surface = match["tour"], match["surface"]
            winner = engine.player(tour, match["winner_id"], surface, day)
            loser = engine.player(tour, match["loser_id"], surface, day)
            if keep:
                found[(match["key"], "winner")] = {f: winner[f] for f in fields}
                found[(match["key"], "loser")] = {f: loser[f] for f in fields}
            if observed:
                pending.append((match, observed, winner, loser))
        for match, observed, winner, loser in pending:
            engine.add(match["tour"], match["winner_id"], match["surface"], day, observed.get("winner", {}), loser)
            engine.add(match["tour"], match["loser_id"], match["surface"], day, observed.get("loser", {}), winner)
    return found


def itf_serve_means(matches):
    """{tour: {stat: (mu, d)}} over scored ITF matches in January-June 2025 (development)."""
    return averages([m for m in matches if m["itf_scope"]], years=SERVE_MEAN_WINDOW)


def phase4_means():
    from matchup_dna.phase4_features import load_settings
    from matchup_dna.elo import RESULTS_DIR
    _, means = load_settings(RESULTS_DIR / "phase4" / "profile_settings.json")
    return means


def build_rows(matches, variant, pool="every_level", means=None, rows_from=ROWS_FROM, profiles=None):
    """Feature rows for every rated scored ITF match from `rows_from`, in replay order. `means` are the profile tour
    averages (default: ITF's own for every_level, Phase 4's for main_only). `profiles` may be passed in, already
    computed for this pool, since they do not depend on the Elo variant."""
    counts = counts_rule(pool)

    def want(match):
        return match["itf_scope"] and match["tourney_date"] >= rows_from

    if profiles is None:
        profiles = pool_profiles(matches, pool, means, rows_from)
    elo, surface = itf_ratings.replay(matches, variant, updates=counts,
                                      keep=lambda m: m["tourney_date"] >= HISTORY_FROM, keep_surface=want)
    history = player_history([m for m in matches if m["tourney_date"] >= HISTORY_FROM], elo, counts, want)
    rows = []
    for prediction in elo:
        match = prediction["match"]
        if not want(match):
            continue
        row = feature_row(prediction, surface[match["key"]], history)
        row.update(tier=match["tier"], tourney_id=match["tourney_id"], split=itf_splits.split_of(match["tourney_date"]),
                   outcome_note=match["outcome_note"] or "")
        sides = ("winner", "loser") if row["a_id"] == match["winner_id"] else ("loser", "winner")
        for letter, side in zip(("a", "b"), sides):
            for field, value in profiles[(match["key"], side)].items():
                row[f"{letter}_{field}"] = value
        rows.append(row)
    return rows


def pool_profiles(matches, pool, means=None, rows_from=ROWS_FROM):
    if means is None:
        means = itf_serve_means(matches) if pool == "every_level" else phase4_means()
    engine = ProfileEngine(means, PROFILE_HALF_LIFE, PROFILE_PRIOR)
    found = {}
    for tour in sorted({m["tour"] for m in matches}):
        found.update(profile_values([m for m in matches if m["tour"] == tour], engine,
                                    lambda m: m["itf_scope"] and m["tourney_date"] >= rows_from, counts_rule(pool)))
    return found

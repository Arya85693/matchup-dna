"""Point-in-time serve and return profiles.

For each player, each statistic is a share: successes over attempts, pooled over earlier matches.

    serve          service points won / service points played
    return         return points won / return points played (the opponent's service points)
    first_in       first serves in / service points
    first_won      points won on first serve / first serves in
    second_won     points won on second serve / second-serve points (service points - first serves in)
    ace            aces / service points
    df             double faults / service points
    bp_saved       break points saved / break points faced      (a match with none faced adds nothing)
    bp_converted   break points won / break-point chances       (a match with no chances adds nothing)

The estimate for a statistic is

    p = (sum of w * successes + m * d * mu) / (sum of w * attempts + m * d)

- w = 0.5 ** (age in weeks / half_life). It weights recent matches more; half_life None means no decay.
- mu is the tour's average share over 2010-2020.
- d is the tour's average attempts per match.
- m is the prior strength in "pseudo-matches": a player with no history gets mu, and a player with many
  matches gets close to their own pooled share. This is the empirical-Bayes (beta-binomial) shrinkage estimate.

Variants:

- surface: the same, using only matches on the surface, shrunk toward the player's overall value.
- recent: a short RECENT_HALF_LIFE, shrunk toward the player's overall value.
- adjusted (serve and return only): each observation is first corrected for the opponent, the one-pass
  Barnett-Clarke adjustment. Serving against opponent j adds n * (r_j - mu_return) to the points won, where
  r_j is j's pre-match return estimate, so winning 65% against strong returners counts for more than 65%
  against weak ones. Returning adds n * (s_j - mu_serve) symmetrically.

Only completed matches contribute. A retirement's statistics may reflect injury, and a walkover has none.
Profiles are replayed one tourney_date at a time: every match on a date sees only earlier dates, and the date's
matches are added afterwards, the Phase 3 rule.
"""
import math
from collections import defaultdict

from matchup_dna.serve_stats import line_problems

STATS = ("serve", "return", "first_in", "first_won", "second_won", "ace", "df", "bp_saved", "bp_converted")
SHARED = ("serve", "return")
RECENT_HALF_LIFE = 8
HALF_LIVES = (26, 52, 104, None)
PRIOR_MATCHES = (1, 2, 4, 8, 16)
MEAN_YEARS = (20100101, 20210101)
HISTORY_START = 19900101


def _whole(line, fields):
    return all(isinstance(line[field], int) for field in fields)


def serve_counts(line):
    """{stat: (successes, attempts)} for the server's own statistics in one valid line; invalid parts are left out."""
    problems = set(line_problems(line))
    found = {}
    if _whole(line, ("svpt", "1stIn", "1stWon", "2ndWon")) and line["svpt"] > 0 and not problems & {
            "first serves in within serve points", "first-serve points won within first serves in",
            "second-serve points won within second-serve points"}:
        svpt, first_in = line["svpt"], line["1stIn"]
        found["serve"] = (line["1stWon"] + line["2ndWon"], svpt)
        found["first_in"] = (first_in, svpt)
        if first_in > 0:
            found["first_won"] = (line["1stWon"], first_in)
        if svpt - first_in > 0:
            found["second_won"] = (line["2ndWon"], svpt - first_in)
        if _whole(line, ("ace",)) and "aces within points won on serve" not in problems:
            found["ace"] = (line["ace"], svpt)
        if _whole(line, ("df",)) and "double faults within second-serve points" not in problems:
            found["df"] = (line["df"], svpt)
    if _whole(line, ("bpSaved", "bpFaced")) and "break points saved within break points faced" not in problems \
            and line["bpFaced"] > 0:
        found["bp_saved"] = (line["bpSaved"], line["bpFaced"])
    return found


def match_observations(match):
    """{"winner": counts, "loser": counts} for a completed match with statistics, else {}."""
    if match.get("outcome") != "completed" or "stats" not in match:
        return {}
    own = {"winner": serve_counts(match["stats"]["w"]), "loser": serve_counts(match["stats"]["l"])}
    found = {}
    for side, other in (("winner", "loser"), ("loser", "winner")):
        counts = dict(own[side])
        if "serve" in own[other]:
            won, played = own[other]["serve"]
            counts["return"] = (played - won, played)
        if "bp_saved" in own[other]:
            saved, faced = own[other]["bp_saved"]
            counts["bp_converted"] = (faced - saved, faced)
        found[side] = counts
    return found if any(found.values()) else {}


def averages(matches, years=MEAN_YEARS):
    """{tour: {stat: (mu, d)}}: the pooled share and the average attempts per contributing match."""
    totals = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for match in matches:
        if not years[0] <= match["tourney_date"] < years[1]:
            continue
        for counts in match_observations(match).values():
            for stat, (successes, attempts) in counts.items():
                entry = totals[match["tour"]][stat]
                entry[0] += successes
                entry[1] += attempts
                entry[2] += 1
    return {tour: {stat: (s / n, n / k) for stat, (s, n, k) in stats.items()} for tour, stats in totals.items()}


def prior_year_averages(matches, window_years=5, min_attempts=10000):
    """Strictly point-in-time tour averages: for a day in year Y, the pooled share and attempts per match over
    completed matches in the `window_years` calendar years before Y. If those years hold under `min_attempts`
    attempts of a statistic, all earlier years are pooled instead; a year with no earlier data at all (the first
    year statistics exist: ATP 1991, WTA 2003) uses its own year. Returns a callable (tour, day) -> {stat: (mu, d)}.
    Used to check the fixed 2010-2020 averages; the frozen model uses the fixed averages."""
    import datetime
    yearly = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for match in matches:
        for counts in match_observations(match).values():
            for stat, (successes, attempts) in counts.items():
                entry = yearly[(match["tour"], match["tourney_date"] // 10000)][stat]
                entry[0] += successes
                entry[1] += attempts
                entry[2] += 1
    cache = {}

    def pooled(tour, years, stat):
        s = n = k = 0
        for year in years:
            entry = yearly.get((tour, year), {}).get(stat)
            if entry:
                s, n, k = s + entry[0], n + entry[1], k + entry[2]
        return (s / n, n / k) if n else None, n

    first_year = {tour: min(y for t, y in yearly if t == tour) for tour in {t for t, _ in yearly}}

    def averages(tour, day):
        year = datetime.date.fromordinal(day).year
        if (tour, year) not in cache:
            found = {}
            for stat in STATS:
                value, attempts = pooled(tour, range(year - window_years, year), stat)
                if attempts < min_attempts:
                    value, attempts = pooled(tour, range(first_year[tour], year), stat)
                if not attempts:
                    value, _ = pooled(tour, (max(year, first_year[tour]),), stat)
                found[stat] = value
            cache[(tour, year)] = found
        return cache[(tour, year)]
    return averages


class Decayed:
    """Sums that lose weight exponentially with time: each is stored with the day it was last updated."""

    def __init__(self, half_life_weeks):
        self.rate = 0.0 if half_life_weeks is None else math.log(2) / (7 * half_life_weeks)
        self.sums = {}

    def get(self, key, day):
        found = self.sums.get(key)
        if found is None:
            return 0.0, 0.0
        successes, attempts, last = found
        factor = math.exp(-self.rate * (day - last))
        return successes * factor, attempts * factor

    def add(self, key, day, successes, attempts):
        old_s, old_n = self.get(key, day)
        self.sums[key] = (old_s + successes, old_n + attempts, day)


class ProfileEngine:
    def __init__(self, means, half_life, prior_matches, recent_half_life=RECENT_HALF_LIFE):
        self.means = means
        self.prior = prior_matches
        self.overall = Decayed(half_life)
        self.surface = Decayed(half_life)
        self.recent = Decayed(recent_half_life)
        self.adjusted = Decayed(half_life)

    def mean(self, tour, stat, day):
        """(mu, d) for a statistic: the fixed tour averages (a dict), or averages that depend on the day (a callable
        taking tour and day, as built by prior_year_averages)."""
        if callable(self.means):
            return self.means(tour, day)[stat]
        return self.means[tour][stat]

    def _shrunk(self, sums, key, day, center, tour, stat):
        successes, attempts = sums.get(key, day)
        weight = self.prior * self.mean(tour, stat, day)[1]
        return (successes + weight * center) / (attempts + weight), attempts

    def player(self, tour, player, surface, day):
        """The player's estimates before `day` (all stats, surface, recent, and adjusted serve and return)."""
        values = {}
        for stat in STATS:
            mu = self.mean(tour, stat, day)[0]
            values[stat], attempts = self._shrunk(self.overall, (tour, player, stat), day, mu, tour, stat)
            values[f"{stat}_attempts"] = attempts
        for stat in SHARED:
            mu = self.mean(tour, stat, day)[0]
            if surface is not None:
                values[f"{stat}_surface"] = self._shrunk(self.surface, (tour, player, surface, stat), day,
                                                         values[stat], tour, stat)[0]
            else:
                values[f"{stat}_surface"] = values[stat]
            values[f"{stat}_recent"] = self._shrunk(self.recent, (tour, player, stat), day, values[stat], tour, stat)[0]
            values[f"{stat}_adjusted"] = self._shrunk(self.adjusted, (tour, player, stat), day, mu, tour, stat)[0]
        return values

    def add(self, tour, player, surface, day, counts, opponent):
        """Adds one match's counts. `opponent` is the opponent's pre-match estimates, used by the adjustment."""
        for stat, (successes, attempts) in counts.items():
            self.overall.add((tour, player, stat), day, successes, attempts)
            if stat in SHARED:
                if surface is not None:
                    self.surface.add((tour, player, surface, stat), day, successes, attempts)
                self.recent.add((tour, player, stat), day, successes, attempts)
                other = "return" if stat == "serve" else "serve"
                shift = opponent[other] - self.mean(tour, other, day)[0]
                self.adjusted.add((tour, player, stat), day, successes + attempts * shift, attempts)


def to_ordinal(date):
    import datetime
    return datetime.date(date // 10000, date // 100 % 100, date % 100).toordinal()


def _binomial_loss(successes, attempts, p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(successes * math.log(p) + (attempts - successes) * math.log(1 - p))


def replay(matches, engine, keep_from=None, score_window=None):
    """Replays profiles one tourney_date at a time.

    Returns (features, scores). features maps (match key, "winner" or "loser") to the player's pre-match
    estimates, for matches dated keep_from or later (none if keep_from is None). scores holds, for matches in
    score_window, the binomial loss per point of forecasting each player's service points won in that match.
    The forecast is the Barnett-Clarke expected share: own serve estimate minus (opponent's return estimate
    minus the tour's average return share), using raw estimates ("raw"), adjusted estimates ("adjusted"),
    or the tour average alone ("tour average").
    """
    by_date = defaultdict(list)
    for match in matches:
        if match["tourney_date"] >= HISTORY_START and match["winner_id"] != match["loser_id"]:
            by_date[match["tourney_date"]].append(match)
    features, scores = {}, defaultdict(lambda: [0.0, 0])
    for date in sorted(by_date):
        day = to_ordinal(date)
        pending = []
        for match in by_date[date]:
            tour, surface = match["tour"], match["surface"]
            winner = engine.player(tour, match["winner_id"], surface, day)
            loser = engine.player(tour, match["loser_id"], surface, day)
            if keep_from is not None and date >= keep_from:
                features[(match["key"], "winner")], features[(match["key"], "loser")] = winner, loser
            observed = match_observations(match)
            if not observed:
                continue
            pending.append((match, observed, winner, loser))
            if score_window and score_window[0] <= date < score_window[1]:
                mu_serve, mu_return = engine.mean(tour, "serve", day)[0], engine.mean(tour, "return", day)[0]
                for side, own, other in (("winner", winner, loser), ("loser", loser, winner)):
                    if "serve" not in observed[side]:
                        continue
                    won, played = observed[side]["serve"]
                    forecasts = {
                        "raw": own["serve"] - (other["return"] - mu_return),
                        "adjusted": own["serve_adjusted"] - (other["return_adjusted"] - mu_return),
                        "tour average": mu_serve,
                    }
                    for name, p in forecasts.items():
                        entry = scores[(tour, name)]
                        entry[0] += _binomial_loss(won, played, p)
                        entry[1] += played
        for match, observed, winner, loser in pending:
            tour, surface = match["tour"], match["surface"]
            engine.add(tour, match["winner_id"], surface, day, observed.get("winner", {}), loser)
            engine.add(tour, match["loser_id"], surface, day, observed.get("loser", {}), winner)
    return features, {key: total / points for key, (total, points) in scores.items()}

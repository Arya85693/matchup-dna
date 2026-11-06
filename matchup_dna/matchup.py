"""A two-player matchup, built from matches strictly before a date, in the same form the models were trained on.

Everything comes from Sackmann's tour-level files (TML backfill is not applied here, which affects statistics
for a few hundred 2025-26 matches). The held-out provider rows are sealed and are never read here.
"""
import math
from collections import defaultdict, deque

from matchup_dna.elo import (
    ELO_K, SURFACE_ELO_K, SURFACE_WEIGHT, START_RATING, blended_rating, expected_score, is_rated, player_ratings,
    run_elo, win_probability,
)
from matchup_dna.features import FORM_MATCHES, PLAYED_OUTCOMES, to_day
from matchup_dna.phase4_features import HEAD_TO_HEAD_SHRINK, load_settings
from matchup_dna.profiles import ProfileEngine, replay, to_ordinal

SACKMANN_LAST_WEEK = 20260525


class History:
    """Everything known before `date` for one tour."""

    def __init__(self, matches, tour, date, settings_path):
        self.tour, self.date = tour, date
        self.matches = [m for m in matches if m["tour"] == tour and m["tourney_date"] < date and m["winner_id"] != m["loser_id"]]
        self.elo_predictions, self.elo = run_elo(self.matches, ELO_K)
        _, self.surface = run_elo(self.matches, SURFACE_ELO_K)
        chosen, means = load_settings(settings_path)
        self.means = means
        self.engine = ProfileEngine(means, chosen[tour]["half_life"], chosen[tour]["prior_matches"])
        replay(self.matches, self.engine)
        self.representation = chosen[tour]["representation"]

    def rank(self, player):
        found = None
        for match in self.matches:
            for side in ("winner", "loser"):
                if match[f"{side}_id"] == player and match[f"{side}_rank"] is not None:
                    found = (match[f"{side}_rank"], match["tourney_date"])
        return found

    def days_since(self, player):
        dates = [m["tourney_date"] for m in self.matches if m["outcome"] in PLAYED_OUTCOMES
                 and player in (m["winner_id"], m["loser_id"])]
        return (to_day(self.date) - to_day(max(dates))).days if dates else None

    def form(self, player):
        recent = deque(maxlen=FORM_MATCHES)
        for prediction in self.elo_predictions:
            match = prediction["match"]
            if player in (match["winner_id"], match["loser_id"]):
                surprise = 1 - win_probability(prediction)
                recent.append(surprise if match["winner_id"] == player else -surprise)
        return (sum(recent) / len(recent) if recent else 0.0), len(recent)

    def head_to_head(self, player, opponent):
        total, meetings = 0.0, 0
        for prediction in self.elo_predictions:
            match = prediction["match"]
            if {match["winner_id"], match["loser_id"]} == {player, opponent}:
                surprise = 1 - win_probability(prediction)
                total += surprise if match["winner_id"] == player else -surprise
                meetings += 1
        return total / (meetings + HEAD_TO_HEAD_SHRINK), meetings

    def snapshot(self, player, surface):
        key = (self.tour, player)
        elo = player_ratings(self.elo, key)
        surface_state = player_ratings(self.surface, key)
        surface_rating = surface_state["surfaces"][surface]["rating"] if surface else None
        blended = blended_rating(surface_state["overall"]["rating"], surface_rating, SURFACE_WEIGHT)
        form, form_matches = self.form(player)
        profile = self.engine.player(self.tour, player, surface, to_ordinal(self.date))
        return {
            "elo": elo["overall"]["rating"], "elo_matches": elo["overall"]["played"],
            "surface_elo_overall": surface_state["overall"]["rating"], "surface_elo_surface": surface_rating,
            "surface_elo_blended": blended,
            "surface_matches": surface_state["surfaces"][surface]["played"] if surface else None,
            "rank": self.rank(player), "days_since": self.days_since(player), "form": form,
            "form_matches": form_matches, "profile": profile,
        }


def matchup_row(history, a, b, surface, best_of):
    """A dataset-shaped row for player a against player b."""
    sa, sb = history.snapshot(a, surface), history.snapshot(b, surface)
    row = {"tour": history.tour, "tourney_date": history.date, "surface": surface or "", "best_of": best_of,
           "a_id": a, "b_id": b, "elo_diff": sa["elo"] - sb["elo"],
           "surface_elo_diff": sa["surface_elo_blended"] - sb["surface_elo_blended"],
           "elo_probability": expected_score(sa["elo"], sb["elo"]),
           "surface_elo_probability": expected_score(sa["surface_elo_blended"], sb["surface_elo_blended"])}
    for letter, snap in (("a", sa), ("b", sb)):
        row[f"{letter}_elo"] = snap["elo"]
        row[f"{letter}_elo_matches"] = snap["elo_matches"]
        row[f"{letter}_surface_matches"] = snap["surface_matches"]
        row[f"{letter}_rank"] = snap["rank"][0] if snap["rank"] else None
        row[f"{letter}_days_since"] = snap["days_since"]
        row[f"{letter}_form"] = snap["form"]
        for field, value in snap["profile"].items():
            row[f"{letter}_{field}"] = value
        row[f"{letter}_recent_games"] = None
    row["h2h_a"], meetings = history.head_to_head(a, b)
    return row, sa, sb, meetings


def profile_interval(p, attempts, prior_weight, z=1.645):
    """An approximate 90% interval for a shrunk share: p +- z * sqrt(p (1 - p) / (attempts + prior weight))."""
    se = math.sqrt(p * (1 - p) / (attempts + prior_weight))
    return p - z * se, p + z * se


def expected_serve(history, server, returner, representation):
    """Barnett-Clarke expected share of service points won by `server` against `returner`."""
    serve, ret = ("serve_adjusted", "return_adjusted") if representation == "adjusted" else ("serve", "return")
    mu_return = history.means[history.tour]["return"][0]
    return server[serve] - (returner[ret] - mu_return)

"""The ITF board's player profiles (web/publisher/itf_players.py) on a tiny synthetic history: the main-tour
profile format, the ITF board's listing rule, readable Flashscore names and the order results are listed in.

    python -m unittest web.publisher.tests.test_itf_players
"""
import datetime
import unittest

from web.publisher import contract, itf_players, players

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def m(date, w, l, rnd="R32", family="itf", scope=True, outcome="completed", day=None, source="sackmann"):
    return {"tour": "ATP", "key": ("ATP", f"t{date}", f"{w}-{l}-{rnd}", rnd, source), "tourney_id": f"t{date}",
            "tourney_name": f"M15 Week {date}", "tourney_level": "15", "tourney_date": date, "surface": "Hard",
            "round": rnd, "best_of": 3, "outcome": outcome, "winner_id": w, "loser_id": l, "winner_rank": None,
            "loser_rank": None, "family": family, "itf_scope": scope, **({"match_day": day} if day else {})}


class ItfPlayersTests(unittest.TestCase):
    def history(self):
        weeks = [20260803, 20260810, 20260817, 20260824, 20260831, 20260907]
        found = [m(d, 1, 2) for d in weeks]                                  # 1 and 2: six ITF matches each
        found += [m(20261005, 1, 3, family="main", scope=False)]             # 3: one main-tour match only
        found += [m(20250106, 4, 2)]                                         # 4: last played in 2025
        found += [m(20261019, 2, 1, "QF", day=20261023), m(20261019, 1, 2, "R16", day=20261021)]
        return found

    def build(self, history):
        history = sorted(history, key=itf_players.played_order)
        predictions, ratings, surface = itf_players.itf_replay(history, 20231111)
        chosen = itf_players.listed_players("ATP", history, ratings, NOW)
        return players.build(history, None, NOW, replay=lambda _: (predictions, ratings, surface),
                             listed=lambda _last: chosen, names={("ATP", 1): "Ann Ace", ("ATP", 2): "B. Base"})

    def test_listed_by_the_itf_board_rule_in_the_main_tour_format(self):
        index, profiles = self.build(self.history())
        self.assertEqual({p["id"] for p in index}, {1, 2})        # 3 and 4 have too few recent ITF matches
        self.assertEqual(sorted(p["elo_rank"] for p in index), [1, 2])
        for doc in profiles.values():
            contract.check_any(doc)
        self.assertEqual(profiles[("ATP", 1)]["name"], "Ann Ace")
        self.assertEqual(profiles[("ATP", 1)]["season"]["All"], [8, 1])   # every level counts in the season record

    def test_recent_results_are_newest_first_within_a_week(self):
        _, profiles = self.build(self.history())
        recent = profiles[("ATP", 1)]["recent"]
        self.assertEqual([(r["round"], r["date"]) for r in recent[:2]], [("QF", "2026-10-23"), ("R16", "2026-10-21")])
        meetings = profiles[("ATP", 1)]["h2h"]["2"]
        self.assertEqual(meetings[0]["round"], "QF")
        self.assertEqual(sum(x["won"] for x in meetings), 7)

    def test_the_order_never_changes_a_rating(self):
        history = self.history()
        _, forward, _ = itf_players.itf_replay(sorted(history, key=itf_players.played_order), 0)
        _, backward, _ = itf_players.itf_replay(list(reversed(sorted(history, key=itf_players.played_order))), 0)
        self.assertEqual(forward, backward)

    def test_listing_keeps_the_board_size(self):
        from matchup_dna.itf_live import BOARD_SIZE
        history = [m(20260803, 1000 + i, 5000 + i) for i in range(BOARD_SIZE + 10) for _ in range(5)]
        _, ratings, _ = itf_players.itf_replay(history, 0)
        self.assertEqual(len(itf_players.listed_players("ATP", history, ratings, NOW)), BOARD_SIZE)

    def test_readable_flashscore_names(self):
        self.assertEqual(itf_players.readable("Wolf J.J."), "J.J. Wolf")
        self.assertEqual(itf_players.readable("Meligeni Alves F."), "F. Meligeni Alves")
        self.assertEqual(itf_players.readable("Kim D.-Y."), "D.-Y. Kim")
        self.assertEqual(itf_players.readable("Dylan Dietrich"), "Dylan Dietrich")


if __name__ == "__main__":
    unittest.main()

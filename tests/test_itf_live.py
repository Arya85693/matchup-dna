"""ITF extension, live pipeline (P2): editions, history, fixtures, placeholders that move nothing, and the store."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from matchup_dna import itf_live as live, itf_model, itf_ratings
from itf_fixtures import matches as history_matches

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 11, 8, 0, tzinfo=UTC)


def fs(mid, start, slug="m15-test", status="finished", outcome="completed", winner="home", home=("p1", "alpha-ann"),
       away=("p2", "beta-bea"), round_="R32", itf=True, tier=1, category="ITF MEN", score="6-3 6-4"):
    return {"provider_match_id": mid, "tour": "ATP", "itf": itf, "category": category, "event": "M15 Test",
            "level": "15" if itf else None, "tier": tier if itf else None, "country": "Spain", "surface": "Clay",
            "round": round_, "start": start, "status": status, "status_detail": "3", "outcome": outcome,
            "winner": winner, "score": score, "retrieved_at": "2026-11-11T07:00:00Z", "slug": slug,
            "page_category": "itf-men-singles" if itf else "challenger-men-singles",
            "home": {"id": home[0], "name": home[1], "slug": home[1], "country": "Spain"},
            "away": {"id": away[0], "name": away[1], "slug": away[1], "country": "Italy"}}


class FakeIds:
    def __init__(self, table):
        self.table = table

    def resolve(self, tour, provider, pid, text, country):
        return self.table.get(pid, ("new_player", -abs(hash(pid)) % 10 ** 9 - 1))


class EditionTests(unittest.TestCase):
    def test_matches_group_into_editions_by_week(self):
        found = live.editions([fs("a", "2026-06-09T10:00:00Z"), fs("b", "2026-06-12T10:00:00Z"),
                               fs("c", "2026-09-15T10:00:00Z")])
        self.assertEqual(found["a"], datetime.date(2026, 6, 8))
        self.assertEqual(found["b"], datetime.date(2026, 6, 8))           # same edition, same Monday
        self.assertEqual(found["c"], datetime.date(2026, 9, 14))          # the slug's next edition

    def test_best_of(self):
        self.assertEqual(live.best_of({"tour": "ATP", "itf": False, "outcome": "completed", "score": "6-4 3-6 6-3 6-4"}), 5)
        self.assertEqual(live.best_of({"tour": "ATP", "itf": True, "outcome": "completed", "score": "6-4 6-3"}), 3)


class HistoryTests(unittest.TestCase):
    def test_flashscore_results_become_history_unless_unresolved_or_already_in_sackmann(self):
        ids = FakeIds({"p1": ("verified", 1), "p2": ("verified", 2), "p3": ("ambiguous", None), "p4": ("verified", 4)})
        matches = [fs("a", "2026-06-09T10:00:00Z"), fs("b", "2026-06-09T12:00:00Z", away=("p3", "x-y")),
                   fs("c", "2026-06-03T10:00:00Z", home=("p4", "d-e"), slug="m15-dup"),
                   fs("d", "2026-06-10T10:00:00Z", status="scheduled", outcome=None, winner=None)]
        index = {("ATP", frozenset((4, 2)), "R32"): [20260601]}
        history, skipped = live.flashscore_history(matches, ids, index, live.editions(matches))
        self.assertEqual([h["provider_match_id"] for h in history], ["a"])
        self.assertEqual(skipped, {"unresolved player": 1, "already in Sackmann": 1})
        h = history[0]
        self.assertEqual((h["winner_id"], h["loser_id"], h["tourney_date"], h["family"], h["itf_scope"]),
                         (1, 2, 20260608, "itf", False))


class FixtureTests(unittest.TestCase):
    def test_only_upcoming_resolved_itf_matches_are_placed(self):
        ids = FakeIds({"p1": ("verified", 1), "p2": ("verified", 2), "p3": ("conflict", None)})
        matches = [fs("up", "2026-11-11T12:00:00Z", status="scheduled", outcome=None, winner=None),
                   fs("late", "2026-11-11T08:03:00Z", status="scheduled", outcome=None, winner=None),
                   fs("who", "2026-11-11T13:00:00Z", status="scheduled", outcome=None, winner=None, away=("p3", "q-r")),
                   fs("chal", "2026-11-11T13:00:00Z", status="scheduled", outcome=None, winner=None, itf=False)]
        ranks = live.rank_index({"ATP": {"2026-11-09": [{"name": "Alpha Ann", "country": "Spain", "rank": 420}],
                                         "2026-11-16": [{"name": "Alpha Ann", "country": "Spain", "rank": 1}]}})
        places, refused = live.fixtures(matches, ids, ranks, live.editions(matches), NOW)
        self.assertEqual([p["provider_match_id"] for p in places], ["up"])
        self.assertEqual(sorted(r for _, r in refused), ["identity verified/conflict", "too_late"])
        p = places[0]
        self.assertEqual((p["winner_rank"], p["loser_rank"]), (420, None))   # the list before the match, not after
        self.assertTrue(p["placeholder"])
        self.assertEqual((p["tourney_date"], p["tier"]), (20261109, 1))


class PlaceholderTests(unittest.TestCase):
    def setUp(self):
        self.history = history_matches(seed=21)
        last = max(m["tourney_date"] for m in self.history)
        self.monday = last + 7 if (last % 100) + 7 <= 28 else last + 100 - (last % 100) + 1

    def placeholder(self, key, a, b, date):
        return {"tour": "ATP", "key": ("ATP", "fs:t", key, "R32", "fixture"), "tourney_id": "fs:t", "tourney_level": "15",
                "tourney_date": date, "surface": "Clay", "round": "R32", "best_of": 3, "outcome": "completed",
                "placeholder": True, "winner_id": a, "loser_id": b, "winner_rank": 300, "loser_rank": None,
                "family": "itf", "itf_scope": True, "tier": 1, "outcome_note": None, "winner_name": "A",
                "loser_name": "B"}

    def test_a_placeholder_moves_nothing(self):
        first = self.placeholder("x1", 1, 2, self.monday)
        later = self.placeholder("x2", 1, 3, self.monday + 1)
        alone = live.placeholder_rows(self.history, [later])[later["key"]]
        with_first = live.placeholder_rows(self.history, [first, later])[later["key"]]
        for field in ("a_elo", "b_elo", "surface_elo_diff", "a_form", "b_form", "a_days_since", "b_days_since",
                      "a_elo_matches", "b_elo_matches"):
            self.assertEqual(alone[field], with_first[field], field)

    def test_placeholder_ratings_are_the_historys_final_ratings(self):
        p = self.placeholder("x1", 1, 2, self.monday)
        row = live.placeholder_rows(self.history, [p])[p["key"]]
        _, ratings = itf_ratings.run_elo(self.history, itf_ratings.VARIANTS["decaying"]["k"])
        a_id = row["a_id"]
        self.assertAlmostEqual(row["a_elo"], ratings[("ATP", a_id)]["rating"])
        self.assertEqual(row["tier"], 1)


class RankTests(unittest.TestCase):
    def test_ranks_match_by_name_and_use_the_country_only_for_namesakes(self):
        index = live.rank_index({"ATP": {"2026-11-09": [
            {"name": "Chepelev Andrey", "country": "Russia", "rank": 610},
            {"name": "Rodrigues Pedro", "country": "Portugal", "rank": 900},
            {"name": "Rodrigues Pedro", "country": "Brazil", "rank": 1200},
            {"name": "Makhlouf Mohamed Nazim", "country": "Algeria", "rank": 1500}]}})
        day = "2026-11-11"
        self.assertEqual(live.lookup_rank(index, "ATP", "chepelev-andrey", "World", day), 610)    # country written differently
        self.assertEqual(live.lookup_rank(index, "ATP", "rodrigues-pedro", "Brazil", day), 1200)
        self.assertIsNone(live.lookup_rank(index, "ATP", "rodrigues-pedro", "Spain", day))          # namesakes, no tie-break
        self.assertEqual(live.lookup_rank(index, "ATP", "makhlouf-nazim", "Algeria", day), 1500)     # a longer form
        self.assertIsNone(live.lookup_rank(index, "ATP", "makhlouf-nazim", "France", day))
        self.assertIsNone(live.lookup_rank(index, "ATP", "chepelev-andrey", "World", "2026-12-15"))  # the list is too old
        self.assertIsNone(live.lookup_rank(index, "ATP", "chepelev-andrey", "World", "2026-11-01"))  # no list before


class BoardTests(unittest.TestCase):
    def test_the_board_lists_active_itf_players_by_rating_with_their_rank(self):
        class Ids(FakeIds):
            players = {("ATP", pid): {"name": f"Player {pid}", "ioc": "ESP"} for pid in range(1, 15)}
            countries = {"Spain": "ESP"}
        today = datetime.datetime(2021, 12, 30, tzinfo=UTC)
        history = history_matches(seed=31, dates=None)
        ids = Ids({"p1": ("verified", 1)})
        seen = [fs("s1", "2021-12-20T10:00:00Z", home=("p1", "player-1"))]
        ranks = live.rank_index({"ATP": {"2021-12-27": [{"name": "Player 1", "country": "Spain", "rank": 321}]}})
        board = live.player_board(history, ids, seen, ranks, today)
        self.assertTrue(board)
        self.assertEqual([r["position"] for r in board], list(range(1, len(board) + 1)))
        self.assertEqual([r["rating"] for r in board], sorted((r["rating"] for r in board), reverse=True))
        self.assertTrue(all(r["wins"] + r["losses"] >= live.BOARD_MIN_MATCHES for r in board))
        one = next(r for r in board if r["id"] == 1)
        self.assertEqual((one["name"], one["country"], one["rank"]), ("Player 1", "ESP", 321))
        itf_played = sum(1 for m in history if m["family"] == "itf" and m["outcome"] in live.PLAYED and m["tourney_date"]
                         >= 20201231 and 1 in (m["winner_id"], m["loser_id"]))
        self.assertEqual(one["wins"] + one["losses"], itf_played)


class StoreTests(unittest.TestCase):
    def test_a_run_issues_both_forecasts_once_settles_and_chains(self):
        from matchup_dna.forecasting.store import Store
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "itf.sqlite", "live")
            self.addCleanup(store.close)
            with store.transaction():
                store.start_run("r1", "itf_forecast", "2026-11-11T08:00:00Z", {})
                store.register_model(live.MODEL_VERSION, "itf_tournament_start", "{}", "m" * 64)
                store.register_model(live.BASELINE_VERSION, "itf_elo_only", "{}", "b" * 64)
                place = {"tour": "ATP", "tourney_id": "fs:itf-men-singles:m15-test:20261109", "tourney_date": 20261109,
                         "event": "M15 Test", "tourney_level": "15", "surface": "Clay", "round": "R32",
                         "provider_match_id": "up", "start": "2026-11-11T12:00:00Z", "identity": ("verified", "new_player"),
                         "winner_id": 1, "loser_id": -5, "winner_name": "Alpha A.", "loser_name": "Beta B.",
                         "home_provider_id": "p1", "away_provider_id": "p2"}
                row = {f: 0 for f in live.INPUT_FIELDS}
                row.update(a_id=-5, b_id=1, a_elo=1500.0, b_elo=1600.0, a_name="Beta B.", b_name="Alpha A.",
                           tour="ATP", surface="Clay", round="R32", tier=1, tourney_date=20261109)
                self.assertEqual(live.issue(store, "r1", NOW, place, row, 0.4, "m" * 64, "b" * 64), "issued")
                store.start_run("r2", "itf_forecast", "2026-11-11T09:00:00Z", {})
                self.assertEqual(live.issue(store, "r2", NOW, place, row, 0.4, "m" * 64, "b" * 64), "unchanged")
                done = fs("up", "2026-11-11T12:00:00Z", winner="away", home=("p1", "alpha-ann"), away=("p2", "beta-bea"))
                ids = FakeIds({"p1": ("verified", 1), "p2": ("new_player", -5)})
                self.assertEqual(live.settle(store, "r1", NOW, [done], ids), 1)
            preds = store.predictions()
            self.assertEqual(sorted(p["model_version"] for p in preds), [live.BASELINE_VERSION, live.MODEL_VERSION])
            baseline = next(p for p in preds if p["model_version"] == live.BASELINE_VERSION)
            self.assertAlmostEqual(baseline["p_a"], 1 / (1 + 10 ** (100 / 400)))
            settled = list(store.settled().values())[0]
            self.assertEqual((settled["status"], settled["winner_id"]), ("completed", -5))
            self.assertEqual(store.verify(), [])
            store.export_ledger(Path(tmp) / "ledger.jsonl")
            self.assertEqual(len((Path(tmp) / "ledger.jsonl").read_text().splitlines()), 2)
            store.close()


class FrozenModelTests(unittest.TestCase):
    def test_the_stored_spec_predicts_what_the_fitted_model_predicts(self):
        from test_itf_experiment import rows
        fit = rows(400)
        model = itf_model.ITFLogistic("M1", 0.0).fit(fit)
        frozen = live.FrozenITF(json.loads(json.dumps(model.spec())))
        test = rows(50, seed=5)
        np.testing.assert_allclose(frozen.predict(test), model.predict(test), rtol=0, atol=1e-15)


if __name__ == "__main__":
    unittest.main()

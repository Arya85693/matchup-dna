"""Phase 6 inference engine: the production feature row for an unplayed fixture is the research row, nothing after the
fixture can reach it, and each model forecasts only when its information exists.

Synthetic ATP history: 30 weekly 8-player editions in 2025, then a target edition in January 2026 with completed
quarterfinals and semifinals to forecast.
"""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from matchup_dna.features import build_rows
from matchup_dna.forecasting import engine
from matchup_dna.forecasting.frozen_models import MODELS_DIR, ROUND_AWARE, TOURNAMENT_START, load_models
from matchup_dna.forecasting.history import Assembly
from matchup_dna.forecasting.records import UTC, iso
from matchup_dna.phase4_features import augment
from matchup_dna.profiles import STATS
from test_round_aware import match as base_match

TARGET = 20260105
GOOD = {"ace": 6, "df": 2, "svpt": 60, "1stIn": 38, "1stWon": 29, "2ndWon": 13, "SvGms": 10, "bpSaved": 2, "bpFaced": 3}
WEAK = {"ace": 3, "df": 4, "svpt": 62, "1stIn": 35, "1stWon": 23, "2ndWon": 10, "SvGms": 10, "bpSaved": 3, "bpFaced": 6}
MODELS_PRESENT = (MODELS_DIR / "phase4_tournament_start.json").exists()


def day(date, plus=0):
    value = datetime.date(date // 10000, date // 100 % 100, date % 100) + datetime.timedelta(days=plus)
    return int(value.strftime("%Y%m%d"))


def m(winner, loser, round_name, number, date, tourney, rank=None):
    match = base_match(winner, loser, round_name, number, date=date, tourney=tourney, draw="8")
    match["stats"] = {"w": dict(GOOD), "l": dict(WEAK)}
    match["w_svpt"], match["l_svpt"] = GOOD["svpt"], WEAK["svpt"]
    match["winner_rank"], match["loser_rank"] = (rank or {}).get(winner, winner * 5), (rank or {}).get(loser, loser * 5)
    match["match_day"] = date
    return match


def edition(players, date, tourney, upset=False):
    """An 8-draw: QF pairs (1v8, 4v5, 3v6, 2v7 by seed order of `players`), the better seed wins unless `upset`."""
    seeds = list(players)
    order = [(0, 7), (3, 4), (2, 5), (1, 6)]
    rows, number, alive = [], 1, []
    for i, j in order:
        w, l = (seeds[j], seeds[i]) if upset and number == 2 else (seeds[i], seeds[j])
        rows.append(m(w, l, "QF", number, date, tourney))
        alive.append(w)
        number += 1
    semis = [(alive[0], alive[1]), (alive[2], alive[3])]
    finalists = []
    for a, b in semis:
        rows.append(m(a, b, "SF", number, date, tourney))
        finalists.append(a)
        number += 1
    rows.append(m(finalists[0], finalists[1], "F", number, date, tourney))
    return rows


def history():
    rows, players = [], list(range(1, 13))
    for week in range(30):
        date = day(20250106, 7 * week)
        chosen = players[week % 4: week % 4 + 8]
        rows += edition(chosen, date, f"E{week}", upset=week % 3 == 0)
    return rows


def target_edition():
    """The target week: QFs 1-8, 4-5, 3-6, 2-7, then SFs 1-4 and 3-2, final 1-3."""
    return edition([1, 2, 3, 4, 5, 6, 7, 8], TARGET, "TARGET")


def settings_file(directory):
    means = {stat: [0.6, 70.0] for stat in STATS}
    means["return"] = [0.4, 70.0]
    payload = {"settings": {tour: {"half_life": 52, "prior_matches": 4, "representation": "adjusted"}
                            for tour in ("ATP", "WTA")},
               "means": {"ATP": means, "WTA": means}}
    path = Path(directory) / "profile_settings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def fixture(home, away, round_name, number, status="verified", start="2026-01-08T12:00:00Z", tourney="TARGET",
            date=TARGET):
    person = lambda pid: {"provider_id": str(pid), "name": f"P{pid}", "rank": pid * 5, "player_id": pid,
                          "status": status, "method": "test"}
    return {"provider": "test", "provider_match_id": str(number), "tour": "ATP", "edition_uid": f"ATP-{date}-{tourney}",
            "td_edition": ["ATP", tourney, date], "tml_edition": None, "tourney_id": tourney, "tourney_date": date,
            "tourney_name": "Test Open", "tourney_level": "A", "surface": "Hard", "best_of": 3, "round": round_name,
            "scheduled_start": start, "match_day": date, "status": "pending", "notes": [],
            "home": person(home), "away": person(away)}


def assembly(matches, fixtures, still_playing=None):
    return Assembly(matches, fixtures, {}, None, None, {}, {}, still_playing or {})


class EngineCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.settings = settings_file(cls.directory.name)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def rows_for(self, matches, fixtures):
        return engine.fixture_rows(matches, fixtures, self.settings)


def oriented(row, low):
    """Model inputs from the lower-id player's side, so rows with different player-A choices can be compared."""
    flip = row["a_id"] != low
    get = lambda a, b: row[b] if flip else row[a]
    sign = -1 if flip else 1
    return {"elo_diff": sign * row["elo_diff"], "surface_elo_diff": sign * row["surface_elo_diff"],
            "rank": (get("a_rank", "b_rank"), get("b_rank", "a_rank")),
            "days": (get("a_days_since", "b_days_since"), get("b_days_since", "a_days_since")),
            "form": (get("a_form", "b_form"), get("b_form", "a_form")),
            "serve": (get("a_serve_adjusted", "b_serve_adjusted"), get("b_serve_adjusted", "a_serve_adjusted")),
            "return": (get("a_return_adjusted", "b_return_adjusted"), get("b_return_adjusted", "a_return_adjusted")),
            "ra_shift": (get("a_ra_elo_shift", "b_ra_elo_shift"), get("b_ra_elo_shift", "a_ra_elo_shift")),
            "ra_share": (get("a_ra_games_won_share", "b_ra_games_won_share"),
                         get("b_ra_games_won_share", "a_ra_games_won_share")),
            "ra": (row["ra_eligible"], row["ra_later_round"])}


class ResearchEquivalenceTests(EngineCase):
    def test_the_fixture_row_is_the_research_row_of_the_same_match(self):
        """A semifinal forecast before it is played has exactly the inputs the research dataset gives that semifinal
        after the whole tournament is known."""
        past = history()
        full = past + target_edition()
        research = {r["match_id"]: r for r in augment(build_rows(full, start=TARGET), full, self.settings, start=TARGET)}
        semi = next(r for r in research.values() if r["round"] == "SF" and {r["a_id"], r["b_id"]} == {1, 4})
        quarterfinals = [x for x in target_edition() if x["round"] == "QF"]
        found = self.rows_for(past + quarterfinals, [fixture(4, 1, "SF", 99)])
        row = next(iter(found.values()))
        self.assertEqual(oriented(row, 1), oriented(semi, 1))
        self.assertEqual(oriented(row, 1)["ra"], (1, 1))
        if MODELS_PRESENT:
            models = load_models()
            for kind in (TOURNAMENT_START, ROUND_AWARE):
                p_fixture = models[kind].predict([row])[0]
                p_research = models[kind].predict([semi])[0]
                to_low = lambda p, r: p if r["a_id"] == 1 else 1 - p
                self.assertAlmostEqual(to_low(p_fixture, row), to_low(p_research, semi), places=12)


class NoLeakageTests(EngineCase):
    def test_the_placeholder_result_never_reaches_the_fixture(self):
        past = history() + [x for x in target_edition() if x["round"] == "QF"]
        one = next(iter(self.rows_for(past, [fixture(1, 4, "SF", 99)]).values()))
        other = next(iter(self.rows_for(past, [fixture(4, 1, "SF", 99)]).values()))
        self.assertEqual(one, other)

    def test_later_results_and_other_editions_change_nothing(self):
        past = history() + [x for x in target_edition() if x["round"] == "QF"]
        base = next(iter(self.rows_for(past, [fixture(1, 4, "SF", 99)]).values()))
        later = edition([1, 2, 3, 4, 5, 6, 7, 8], day(TARGET, 7), "NEXT-WEEK")
        same_week_elsewhere = edition([9, 10, 11, 12, 5, 6, 7, 8], TARGET, "OTHER-EVENT")
        changed = next(iter(self.rows_for(past + later + same_week_elsewhere, [fixture(1, 4, "SF", 99)]).values()))
        self.assertEqual(base, changed)

    def test_other_fixtures_in_the_same_round_do_not_change_each_other(self):
        past = history() + [x for x in target_edition() if x["round"] == "QF"]
        alone = self.rows_for(past, [fixture(1, 4, "SF", 99)])
        together = self.rows_for(past, [fixture(1, 4, "SF", 99), fixture(3, 2, "SF", 98)])
        key = next(iter(alone))
        self.assertEqual(alone[key], together[key])


class EligibilityTests(EngineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.models = load_models() if MODELS_PRESENT else None

    def decide(self, matches, item, issued="2026-01-08T08:00:00Z", still_playing=None):
        rows = self.rows_for(matches, [item])
        row = rows.get(engine.fixture_uid(item))
        context = assembly(matches, [item], still_playing)
        return {kind: engine.decide(item, row, model, issued, context) for kind, model in self.models.items()}

    @unittest.skipUnless(MODELS_PRESENT, "model artifacts not exported")
    def test_a_first_round_match_gets_only_the_tournament_start_forecast(self):
        found = self.decide(history(), fixture(1, 8, "QF", 1))
        self.assertEqual(found[TOURNAMENT_START], ("issued", "eligible"))
        self.assertEqual(found[ROUND_AWARE][0], "ineligible")
        self.assertIn("first match", found[ROUND_AWARE][1])

    @unittest.skipUnless(MODELS_PRESENT, "model artifacts not exported")
    def test_a_later_round_with_complete_earlier_rounds_gets_both(self):
        past = history() + [x for x in target_edition() if x["round"] == "QF"]
        found = self.decide(past, fixture(1, 4, "SF", 99))
        self.assertEqual(found[TOURNAMENT_START][0], "issued")
        self.assertEqual(found[ROUND_AWARE][0], "issued")

    @unittest.skipUnless(MODELS_PRESENT, "model artifacts not exported")
    def test_a_missing_earlier_round_blocks_only_the_round_aware_forecast(self):
        quarterfinals = [x for x in target_edition() if x["round"] == "QF" and 4 not in (x["winner_id"], x["loser_id"])]
        found = self.decide(history() + quarterfinals, fixture(1, 4, "SF", 99))
        self.assertEqual(found[TOURNAMENT_START][0], "issued")
        self.assertEqual(found[ROUND_AWARE][0], "ineligible")
        self.assertIn("earlier rounds unusable", found[ROUND_AWARE][1])

    @unittest.skipUnless(MODELS_PRESENT, "model artifacts not exported")
    def test_unverified_identities_are_not_forecast(self):
        for status in ("ambiguous", "conflict"):
            found = self.decide(history(), fixture(1, 8, "QF", 1, status=status))
            self.assertEqual({d for d, _ in found.values()}, {"ineligible"}, status)
        found = self.decide(history(), fixture(1, 8, "QF", 1, status="new_player"))
        self.assertEqual(found[TOURNAMENT_START][0], "issued")

    @unittest.skipUnless(MODELS_PRESENT, "model artifacts not exported")
    def test_late_and_incomplete_forecasts_are_refused_not_guessed(self):
        late = self.decide(history(), fixture(1, 8, "QF", 1, start="2026-01-08T08:20:00Z"))
        self.assertEqual({d for d, _ in late.values()}, {"too_late"})
        deferred = self.decide(history(), fixture(1, 8, "QF", 1),
                               still_playing={("ATP", 8): [(day(TARGET, -7), "E-LAST")]})
        self.assertEqual({d for d, _ in deferred.values()}, {"deferred"})


@unittest.skipUnless(MODELS_PRESENT, "model artifacts not exported")
class ReproductionTests(EngineCase):
    def test_a_stored_forecast_is_recomputed_exactly_from_its_own_snapshot(self):
        models = load_models()
        past = history() + [x for x in target_edition() if x["round"] == "QF"]
        item = fixture(1, 4, "SF", 99)
        row = self.rows_for(past, [item])[engine.fixture_uid(item)]
        for model in models.values():
            content = engine.prediction_content(engine.fixture_uid(item), item, row, model,
                                                "2026-01-08T08:00:00Z", "run", "replay", {}, "commit", "code")
            stored = json.loads(json.dumps(content))  # as it comes back from the database
            self.assertEqual(engine.reproduce(stored, model), content["p_a"])
            terms = sum(stored["inputs"]["contributions"].values())
            self.assertAlmostEqual(1 / (1 + 2.718281828459045 ** -terms), content["p_a"], places=9)

    def test_the_input_hash_follows_the_model_inputs_only(self):
        model = load_models()[TOURNAMENT_START]
        past = history() + [x for x in target_edition() if x["round"] == "QF"]
        item = fixture(1, 4, "SF", 99)
        row = self.rows_for(past, [item])[engine.fixture_uid(item)]
        content = lambda r: engine.prediction_content("M", item, r, model, "2026-01-08T08:00:00Z", "run", "replay",
                                                      {}, "c", "s")
        same = dict(row, h2h_a=0.3)  # not a model input
        changed = dict(row, a_rank=row["a_rank"] + 50)
        self.assertEqual(content(row)["input_sha256"], content(same)["input_sha256"])
        self.assertNotEqual(content(row)["input_sha256"], content(changed)["input_sha256"])


if __name__ == "__main__":
    unittest.main()

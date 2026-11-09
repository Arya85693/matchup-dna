"""Phase 6 end to end on synthetic provider rows: fixtures in, forecasts stored before the match, re-runs idempotent,
results attached without touching the forecasts, the website payload honest about which model has a forecast."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from matchup_dna.forecasting import api, pipeline, prospective
from matchup_dna.forecasting.frozen_models import MODELS_DIR
from matchup_dna.forecasting.records import UTC
from matchup_dna.forecasting.store import Store
from test_forecast_engine import settings_file
from test_forecast_history import scheduled, sources
from test_heldout import td_row, tml, umag

AS_OF = datetime.datetime(2026, 7, 15, 6, 0, tzinfo=UTC)
MODELS_PRESENT = (MODELS_DIR / "phase4_tournament_start.json").exists()


def scenario(result=None):
    """Umag R32 (TML and TD), then two fixtures on 15 July: an R16 between two R32 winners (Sinner, Merida) and a
    late R32 that neither player has started (Sesko, Etcheverry). `result` = (TD winner code, TML winner) plays the
    R16."""
    tml_rows, td_rows, tml_links, td_links = umag()
    tml_rows, td_rows = tml_rows[:2], td_rows[:2]
    td_links[("ATP", "106262")] = 106262
    r16 = td_row(30, "2026-07-15", "Sinner J.", "206173", "Merida Aguilar D.", "122001", round_name="R16")
    r16["date_timestamp"] = str(int(datetime.datetime(2026, 7, 15, 12, 0, tzinfo=UTC).timestamp()))
    r32 = td_row(31, "2026-07-15", "Etcheverry T. M.", "144869", "Arias B.", "106262")
    r32["date_timestamp"] = str(int(datetime.datetime(2026, 7, 15, 14, 0, tzinfo=UTC).timestamp()))
    if result is None:
        td_rows += [scheduled(r16), scheduled(r32)]
    else:
        td_code, tml_winner = result
        r16.update(winner_code=td_code)
        td_rows += [r16, scheduled(r32)]
        winner, loser = ("Jannik Sinner", "S0AG"), ("Daniel Merida", "M0N7")
        if tml_winner != "Sinner":
            winner, loser = loser, winner
        tml_rows.append(tml(20260715, winner[0], winner[1], loser[0], loser[1], number="16", round_name="R16"))
    return sources(tml_rows, td_rows, tml_links, td_links)


@unittest.skipUnless(MODELS_PRESENT, "model artifacts not exported")
class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = settings_file(self.directory.name)
        self.store = Store(Path(self.directory.name) / "replay.sqlite", mode="replay")  # July 2026 is the past
        self.ledger = Path(self.directory.name) / "ledger.jsonl"

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def forecast(self, data, as_of=AS_OF):
        return pipeline.forecast(self.store, data, as_of, settings=self.settings, ledger_path=self.ledger,
                                 reviews_path=Path(self.directory.name) / "none.csv")

    def test_forecast_rerun_settle_and_score(self):
        _, counts = self.forecast(scenario())
        self.assertEqual(counts["tournament_start: issued"], 2)
        self.assertEqual(counts["round_aware: issued"], 1)       # the R16; the R32 is a first match
        self.assertEqual(counts["round_aware: ineligible"], 1)
        stored = self.store.predictions()
        self.assertEqual(len(stored), 3)

        _, again = self.forecast(scenario(), AS_OF + datetime.timedelta(minutes=10))
        self.assertEqual(again["tournament_start: unchanged"], 2)
        self.assertEqual(again["round_aware: unchanged"], 1)
        self.assertEqual(len(self.store.predictions()), 3)
        self.assertEqual(len(self.ledger.read_text(encoding="utf-8").splitlines()), 3)
        self.assertEqual(api.verify_store(self.store), [])

        payload = api.upcoming(self.store, AS_OF)
        late_r32 = next(m for m in payload["matches"] if m["round"] == "R32")
        self.assertFalse(late_r32["forecasts"]["round_aware"]["available"])
        self.assertNotIn("probabilities", late_r32["forecasts"]["round_aware"])
        self.assertIn("first match", late_r32["forecasts"]["round_aware"]["reason"])
        r16 = next(m for m in payload["matches"] if m["round"] == "R16")
        for kind in ("tournament_start", "round_aware"):
            probabilities = r16["forecasts"][kind]["probabilities"]
            self.assertAlmostEqual(sum(probabilities.values()), 1.0, places=12)
            self.assertEqual(set(probabilities), {"206173", "210017"})

        _, settled = pipeline.settle(self.store, scenario(("1", "Sinner")), AS_OF + datetime.timedelta(hours=8))
        self.assertEqual(settled["matches with a result"], 1)
        settlement = self.store.settled()
        r16_uid = r16["match_uid"]
        self.assertEqual((settlement[r16_uid]["state"], settlement[r16_uid]["winner_id"]), ("settled", 206173))
        self.assertEqual({o["source"] for o in self.store.outcomes(r16_uid)}, {"tml", "tennisdata_app"})
        self.assertEqual([p["p_a"] for p in self.store.predictions()], [p["p_a"] for p in stored])
        lines = "\n".join(prospective.score_store(self.store))
        self.assertIn("tournament_start (all counted): n 1", lines)
        self.assertIn("R0 minus tournament start, same later-round matches", lines)

    def test_sources_that_disagree_leave_the_match_unscored(self):
        self.forecast(scenario())
        pipeline.settle(self.store, scenario(("2", "Sinner")), AS_OF + datetime.timedelta(hours=8))
        states = {s["state"] for s in self.store.settled().values()}
        self.assertEqual(states, {"conflict"})
        rows, excluded = prospective.rows_by_kind(self.store)
        self.assertEqual(rows, {})
        self.assertEqual(sum(excluded.values()), 1 + 1 + 1)  # 2 R16 forecasts in conflict, the R32 has no result

    def test_a_live_store_refuses_a_backdated_or_future_issue_time(self):
        live = Store(Path(self.directory.name) / "live.sqlite", mode="live")
        for when in (AS_OF, datetime.datetime.now(UTC) + datetime.timedelta(hours=1)):
            with self.assertRaises(ValueError):
                pipeline.forecast(live, scenario(), when, settings=self.settings)
        self.assertEqual(live.predictions(), [])
        live.close()

    def test_a_match_already_started_gets_no_forecast(self):
        _, counts = self.forecast(scenario(), datetime.datetime(2026, 7, 15, 11, 45, tzinfo=UTC))
        self.assertEqual(counts["tournament_start: too_late"], 1)   # the 12:00 R16
        self.assertEqual(counts["tournament_start: issued"], 1)     # the 14:00 R32


if __name__ == "__main__":
    unittest.main()

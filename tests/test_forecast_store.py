"""Phase 6 storage: forecasts and results cannot be changed or removed, re-runs write nothing new, and the hash chain
and ledger expose any tampering."""
import datetime
import sqlite3
import tempfile
import unittest
from pathlib import Path

from matchup_dna.forecasting.records import UTC, canonical_json, sha256_text
from matchup_dna.forecasting.store import Store, StoreError

T0 = datetime.datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
ARTIFACT = '{"model_version": "m-1"}'


def content(match_uid="M-1", p=0.6, features=None, issued="2026-11-09T08:00:00Z"):
    features = features or {"elo_logit": 0.1}
    return {"schema": 1, "mode": "live", "match_uid": match_uid, "model_version": "m-1",
            "model_sha256": sha256_text(ARTIFACT), "model_kind": "tournament_start", "run_id": "run-1",
            "issued_at": issued, "scheduled_start": "2026-11-09T12:00:00Z", "player_a": 1, "player_b": 2, "p_a": p,
            "input_sha256": sha256_text(canonical_json(features)), "inputs": {"features": features},
            "code_commit": "x", "code_sha256": "y"}


def ready_store(path=":memory:", mode="live"):
    store = Store(path, mode=mode)
    store.start_run("run-1", "forecast", T0, {})
    store.register_model("m-1", "tournament_start", ARTIFACT, sha256_text(ARTIFACT))
    store.ensure_edition("E-1", "ATP", "Test Open", 20261109, "A", "Hard", T0)
    for uid, low, high in (("M-1", 1, 2), ("M-2", 3, 4)):
        store.ensure_match(uid, "ATP", "E-1", "R32", low, high, T0)
    return store


class AppendOnlyTests(unittest.TestCase):
    def test_a_stored_forecast_cannot_be_updated_or_deleted(self):
        store = ready_store()
        store.add_prediction(content())
        with self.assertRaises(sqlite3.DatabaseError):
            store.db.execute("UPDATE predictions SET p_a = 0.9")
        with self.assertRaises(sqlite3.DatabaseError):
            store.db.execute("DELETE FROM predictions")
        self.assertEqual(store.predictions()[0]["p_a"], 0.6)

    def test_results_and_evidence_tables_are_append_only(self):
        store = ready_store()
        store.add_outcome("M-1", "tml", "1", "completed", 1, "6-4 6-4", 3, T0, T0, "run-1")
        store.add_decision("run-1", "M-1", "m-1", T0, "ineligible", "test")
        for statement in ("UPDATE outcomes SET winner_id = 2", "DELETE FROM outcomes",
                          "UPDATE eligibility_decisions SET reason = 'x'", "DELETE FROM model_versions",
                          "UPDATE matches SET player_low = 0", "DELETE FROM editions"):
            with self.assertRaises(sqlite3.DatabaseError, msg=statement):
                store.db.execute(statement)


class IdempotencyTests(unittest.TestCase):
    def test_the_same_inputs_write_nothing_new(self):
        store = ready_store()
        first = store.add_prediction(content())
        again = store.add_prediction(content(issued="2026-11-09T09:00:00Z"))
        self.assertEqual(first[0], "issued")
        self.assertEqual(again, ("unchanged", first[1]))
        self.assertEqual(len(store.predictions()), 1)

    def test_changed_inputs_add_a_new_forecast_that_names_the_old_one(self):
        store = ready_store()
        _, old = store.add_prediction(content())
        status, new = store.add_prediction(content(p=0.55, features={"elo_logit": 0.05}))
        self.assertEqual(status, "issued")
        rows = store.predictions()
        self.assertEqual([r["prediction_id"] for r in rows], [old, new])
        self.assertEqual(rows[1]["supersedes"], old)
        self.assertEqual(rows[0]["p_a"], 0.6)  # the original is kept as issued

    def test_an_unregistered_or_changed_model_is_refused(self):
        store = ready_store()
        bad = dict(content(), model_sha256="0" * 64)
        with self.assertRaises(StoreError):
            store.add_prediction(bad)
        with self.assertRaises(StoreError):
            store.register_model("m-1", "tournament_start", '{"changed": true}', sha256_text('{"changed": true}'))

    def test_one_real_match_has_one_canonical_row(self):
        store = ready_store()
        self.assertFalse(store.ensure_match("M-1", "ATP", "E-1", "R32", 1, 2, T0))
        with self.assertRaises(StoreError):
            store.ensure_match("M-other", "ATP", "E-1", "R32", 1, 2, T0)
        with self.assertRaises(StoreError):
            store.ensure_match("M-3", "ATP", "E-1", "R32", 2, 1, T0)  # players must be ordered
        store.add_match_alias("tennisdata_app", "ATP", "77", "M-1", T0)
        with self.assertRaises(StoreError):
            store.add_match_alias("tennisdata_app", "ATP", "77", "M-2", T0)


class IntegrityTests(unittest.TestCase):
    def test_the_chain_verifies_and_detects_a_forced_change(self):
        store = ready_store()
        store.add_prediction(content())
        store.add_prediction(content(match_uid="M-2"))
        self.assertEqual(store.verify(), [])
        store.db.execute("DROP TRIGGER predictions_no_update")  # someone bypasses the guard
        store.db.execute("UPDATE predictions SET p_a = 0.99 WHERE seq = 1")
        self.assertTrue(any("p_a" in problem for problem in store.verify()))

    def test_the_ledger_only_grows(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            store = ready_store()
            store.add_prediction(content())
            self.assertEqual(store.export_ledger(ledger), 1)
            store.add_prediction(content(match_uid="M-2"))
            self.assertEqual(store.export_ledger(ledger), 2)
            other = ready_store()  # a different history: its first forecast differs from the committed one
            other.add_prediction(content(p=0.7))
            with self.assertRaises(StoreError):
                other.export_ledger(ledger)
            self.assertEqual(len(ledger.read_text(encoding="utf-8").splitlines()), 2)

    def test_live_and_replay_stores_never_mix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "s.sqlite"
            Store(path, mode="replay").close()
            with self.assertRaises(StoreError):
                Store(path, mode="live")
            with self.assertRaises(StoreError):
                Store(Path(directory) / "new.sqlite")  # a new store must say which it is


class SettlementTests(unittest.TestCase):
    def test_agreeing_sources_settle_and_disagreeing_ones_conflict(self):
        store = ready_store()
        store.add_outcome("M-1", "tml", "1", "completed", 1, "6-4 6-4", 3, T0, T0, "run-1")
        store.add_outcome("M-1", "tennisdata_app", "9", "completed", 1, "6-4 6-4", 3, T0, T0, "run-1")
        store.add_outcome("M-2", "tml", "2", "completed", 3, "6-4 6-4", 3, T0, T0, "run-1")
        store.add_outcome("M-2", "tennisdata_app", "8", "completed", 4, "6-4 6-4", 3, T0, T0, "run-1")
        settled = store.settled()
        self.assertEqual((settled["M-1"]["state"], settled["M-1"]["winner_id"]), ("settled", 1))
        self.assertEqual(settled["M-2"]["state"], "conflict")
        self.assertFalse(store.add_outcome("M-1", "tml", "1", "completed", 1, "6-4 6-4", 3, T0, T0, "run-1"))

    def test_a_result_without_a_retrieval_time_is_refused_and_cancellations_are_not_repeated(self):
        store = ready_store()
        with self.assertRaises(StoreError):
            store.add_outcome("M-1", "tml", "1", "completed", 1, "6-4 6-4", 3, None, T0, "run-1")
        self.assertTrue(store.add_outcome("M-2", "tennisdata_app", "9", "cancelled", None, None, 3, T0, T0, "run-1"))
        self.assertFalse(store.add_outcome("M-2", "tennisdata_app", "9", "cancelled", None, None, 3, T0, T0, "run-1"))
        self.assertEqual(len(store.outcomes("M-2")), 1)
        with self.assertRaises(sqlite3.IntegrityError):  # a broken row fails loudly, it is never silently skipped
            store.add_match_alias("tennisdata_app", "ATP", "5", "M-unknown", T0)


if __name__ == "__main__":
    unittest.main()

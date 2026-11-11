"""Phase 7 publisher tests. They build synthetic stores in temporary folders with the Phase 6 test scenario; no test
opens data/store/live.sqlite.

    python -m unittest discover -s web/publisher/tests -t .
"""
import ast
import contextlib
import datetime
import io
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))      # the Phase 6 synthetic scenario lives with the existing tests

from matchup_dna.forecasting import pipeline, prospective                       # noqa: E402
from matchup_dna.forecasting.store import Store                                 # noqa: E402
from test_forecast_engine import settings_file                                  # noqa: E402
from test_forecast_pipeline import AS_OF, MODELS_PRESENT, scenario              # noqa: E402
from web.publisher import contract, publish, reasons, views                     # noqa: E402
from web.publisher.readonly import ReadOnlyError, copy_store, open_readonly     # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_protocol():
    """The real P1 protocol with its window moved back to cover the July 2026 scenario."""
    protocol = json.loads(json.dumps(prospective.load_protocol()))
    protocol["window"]["issued_from"] = "2026-07-01T00:00:00Z"
    return protocol


class ReasonTests(unittest.TestCase):
    def test_every_engine_reason_has_plain_words(self):
        cases = {
            ("deferred", "no confirmed start time yet (forecast once the provider publishes one)"): "start_unconfirmed",
            ("ineligible", "neither player has played earlier in this edition (first match): nothing for R0 to add"):
                "ra_first_match",
            ("ineligible", "round RR: R0 covers knockout rounds only"): "ra_round_robin",
            ("too_late", "the match is already in progress"): "too_late_in_progress",
            ("too_late", "the match has already been played (a source reports its result)"): "too_late_played",
            ("too_late", "issued 2026-11-09T05:10:00Z, less than 0:30:00 before the scheduled start"): "too_late",
            ("ineligible", "identity ambiguous for Some Player (compatible name)"): "identity_review",
            (None, None): "not_evaluated",
        }
        for (decision, reason), code in cases.items():
            self.assertEqual(reasons.describe(decision, reason)[0], code, reason)

    def test_unknown_reason_is_shown_not_hidden(self):
        code, text = reasons.describe("ineligible", "format best-of-1 is outside the models' population")
        self.assertEqual(code, "other")
        self.assertIn("best-of-1", text)

    def test_identity_method_stays_private(self):
        _, text = reasons.describe("ineligible", "identity conflict for X (linked ESPN matches name two players)")
        self.assertNotIn("ESPN", text)


class ReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "store.sqlite"
        Store(self.path, mode="live").close()

    def tearDown(self):
        self.directory.cleanup()

    def test_cannot_write(self):
        before = sha(self.path)
        store = open_readonly(self.path)
        with self.assertRaises(sqlite3.OperationalError):
            store.db.execute("INSERT INTO schema_info VALUES ('x', 'y')")
        store.close()
        self.assertEqual(sha(self.path), before)

    def test_missing_store_is_not_created(self):
        missing = Path(self.directory.name) / "nope.sqlite"
        with self.assertRaises(ReadOnlyError):
            open_readonly(missing)
        self.assertFalse(missing.exists())

    def test_copy_leaves_source_unchanged(self):
        before = sha(self.path)
        copy = copy_store(self.path, Path(self.directory.name) / "copy.sqlite")
        self.assertEqual(open_readonly(copy).mode, "live")
        self.assertEqual(sha(self.path), before)

    def test_run_in_progress_skips(self):
        store = Store(self.path)
        store.start_run("forecast-x", "forecast", AS_OF, {})
        store.close()
        with self.assertRaises(publish.Skipped):
            publish.publish(self.path, Path(self.directory.name) / "out", now=AS_OF, protocol=test_protocol())


@unittest.skipUnless(MODELS_PRESENT, "model artifacts not exported")
class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        base = Path(self.directory.name)
        self.path = base / "replay.sqlite"
        store = Store(self.path, mode="replay")
        pipeline.forecast(store, scenario(), AS_OF, settings=settings_file(self.directory.name),
                          ledger_path=base / "ledger.jsonl", reviews_path=base / "none.csv")
        self.store = store
        self.out = base / "out"

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def publish(self, now=AS_OF):
        return publish.publish(self.path, self.out, now=now, allow_replay=True, protocol=test_protocol())

    def read(self, manifest, name):
        return json.loads((self.out / "v1" / manifest["snapshot"] / name).read_text(encoding="utf-8"))

    def test_store_unchanged_and_files_match_manifest(self):
        before = sha(self.path)
        manifest = self.publish()
        self.assertEqual(sha(self.path), before)
        for name, digest in manifest["files"].items():
            self.assertEqual(sha(self.out / "v1" / manifest["snapshot"] / name), digest, name)
        self.assertTrue(manifest["code_matches_protocol"])

    def test_refuses_replay_store_by_default(self):
        with self.assertRaises(SystemExit):
            publish.publish(self.path, self.out, now=AS_OF, protocol=test_protocol())

    def test_model_b_never_borrows_model_a(self):
        index = self.read(self.publish(), "matches/index.json")
        r16 = next(m for m in index["matches"] if m["round"] == "R16")
        r32 = next(m for m in index["matches"] if m["round"] == "R32")
        self.assertTrue(r16["forecasts"]["round_aware"]["available"])
        self.assertTrue(r32["forecasts"]["tournament_start"]["available"])
        self.assertFalse(r32["forecasts"]["round_aware"]["available"])
        self.assertNotIn("p", r32["forecasts"]["round_aware"])
        self.assertEqual(r32["forecasts"]["round_aware"]["reason_code"], "ra_first_match")

    def test_headline_is_the_counted_forecast(self):
        index = self.read(self.publish(), "matches/index.json")
        stored = {r["prediction_id"]: r for r in self.store.predictions()}
        counted = views.counted(self.store, test_protocol())
        for m in index["matches"]:
            for kind, f in m["forecasts"].items():
                if f["available"]:
                    row = stored[f["prediction_id"]]
                    self.assertTrue(f["counted"])
                    self.assertEqual(counted[(m["uid"], row["model_version"])]["prediction_id"], f["prediction_id"])
                    p_first = row["p_a"] if row["player_a"] == m["players"][0]["id"] else 1 - row["p_a"]
                    self.assertEqual(f["p"][0], p_first)

    def test_match_page_contributions_reproduce_probability(self):
        manifest = self.publish()
        r16 = next(m for m in self.read(manifest, "matches/index.json")["matches"] if m["round"] == "R16")
        page = self.read(manifest, f"matches/{r16['uid']}.json")
        for kind in ("tournament_start", "round_aware"):
            v = page["versions"][kind][0]
            self.assertAlmostEqual(1 / (1 + 2.718281828459045 ** -v["log_odds"]), v["p"][0], places=9)
            self.assertTrue(v["integrity"]["code_matches_protocol"])
        self.assertIn("games_won_share_this_event", page["versions"]["round_aware"][0]["inputs"][0])
        self.assertNotIn("games_won_share_this_event", page["versions"]["tournament_start"][0]["inputs"][0])

    def test_track_record_uses_protocol_counting(self):
        pipeline.settle(self.store, scenario(("1", "Sinner")), AS_OF + datetime.timedelta(hours=8))
        record = self.read(self.publish(AS_OF + datetime.timedelta(hours=9)), "research/track-record.json")
        self.assertTrue(record["interim"])
        self.assertEqual(record["counts"]["scored"], {"tournament_start": 1, "round_aware": 1})
        self.assertEqual(record["round_aware_minus_tournament_start"]["n"], 1)
        rows, _ = prospective.outcome_rows(self.store, views.counted(self.store, test_protocol()))
        a = [r for r in rows if r["model_kind"] == "tournament_start"]
        self.assertAlmostEqual(record["tournament_start"]["all"]["log_loss"],
                               float(prospective.match_log_loss([a[0]["p"]], [a[0]["y"]])[0]), places=12)

    def test_archive_lists_every_forecast_once(self):
        archive = self.read(self.publish(), "archive.json")
        stored = {r["prediction_id"] for r in self.store.predictions()}
        self.assertEqual({e["prediction_id"] for e in archive["entries"]}, stored)
        self.assertEqual(len(archive["entries"]), len(stored))
        self.assertTrue(all(abs(sum(e["p"]) - 1) < 1e-12 for e in archive["entries"]))
        import math
        for e in archive["entries"]:                           # the inspection data reproduces each stored probability
            self.assertAlmostEqual(1 / (1 + math.exp(-sum(v for _, v in e["contributions"]))), e["p"][0], places=9)
            self.assertTrue(e["issued_before_start"])

    def test_players_come_only_from_forecasts(self):
        manifest = self.publish()
        players = self.read(manifest, "players.json")["players"]
        index = self.read(manifest, "matches/index.json")["matches"]
        forecast_ids = {p["id"] for m in index if m["forecasts"]["tournament_start"]["available"] for p in m["players"]}
        self.assertEqual({p["id"] for p in players}, forecast_ids)
        for p in players:
            self.assertEqual(set(p["latest"]["inputs"]), set(views.PROFILE_INPUTS))

    def test_nothing_private_is_published(self):
        manifest = self.publish()
        for name in manifest["files"]:
            text = (self.out / "v1" / manifest["snapshot"] / name).read_text(encoding="utf-8")
            for secret in ("run_id", "content_json", "provider_match_id", "identity_method", str(ROOT), ".sqlite"):
                self.assertNotIn(secret, text, f"{secret} in {name}")


class CloudGateTests(unittest.TestCase):
    """scripts/cloud/gate.py: when GitHub Actions runs have work to do (Phase 8)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts" / "cloud" / "gate.py")
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)

    def at(self, text):
        return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc)

    def test_eastern_time_and_daylight_saving(self):
        g = self.gate
        self.assertEqual(g.eastern_offset(self.at("2026-07-01 12:00")), datetime.timedelta(hours=-4))
        self.assertEqual(g.eastern_offset(self.at("2026-12-01 12:00")), datetime.timedelta(hours=-5))
        self.assertEqual(g.eastern_offset(self.at("2026-03-08 06:59")), datetime.timedelta(hours=-5))   # 01:59 EST
        self.assertEqual(g.eastern_offset(self.at("2026-03-08 07:00")), datetime.timedelta(hours=-4))   # 03:00 EDT
        self.assertEqual(g.eastern_offset(self.at("2026-11-01 05:59")), datetime.timedelta(hours=-4))
        self.assertEqual(g.eastern_offset(self.at("2026-11-01 06:00")), datetime.timedelta(hours=-5))
        # 07:00 Eastern is 12:00 UTC in winter and 11:00 UTC in summer; 19:00 Eastern is 00:00 / 23:00 UTC.
        self.assertEqual(g.latest_slot(self.at("2026-11-10 12:30")), self.at("2026-11-10 12:00"))
        self.assertEqual(g.latest_slot(self.at("2026-07-10 11:30")), self.at("2026-07-10 11:00"))
        self.assertEqual(g.latest_slot(self.at("2026-11-10 00:20")), self.at("2026-11-10 00:00"))
        self.assertEqual(g.latest_slot(self.at("2026-11-10 11:59")), self.at("2026-11-10 00:00"))

    def test_preflight_tolerates_processor_rounding_only(self):
        from unittest import mock
        g = self.gate
        store = mock.Mock(mode="live")
        findings = {
            "rounding": ["94cff5deeace: recomputed 0.6499868570461047, stored 0.6499868570461048"],
            "changed": ["94cff5deeace: recomputed 0.6499, stored 0.6500"],
            "chain": ["chain broken at seq 5"],
        }
        for case, found in findings.items():
            with self.subTest(case), mock.patch("matchup_dna.forecasting.api.verify_store", return_value=found), \
                    mock.patch("web.publisher.readonly.open_readonly", return_value=store):
                problems, notes = g.preflight("unused.sqlite")
                if case == "rounding":
                    self.assertEqual(problems, [])
                    self.assertEqual(len(notes), 1)
                else:
                    self.assertEqual(problems, found)                 # a real difference or a broken chain stops the run

    def test_status_page_judges_integrity_by_the_preflight_rule(self):
        """The site showed "Data may be out of date" and "1 issues" on 10-11 November while every run succeeded: its
        status view counted the processor-rounding note that the preflight lets through. Both now use one rule."""
        from unittest import mock
        snap = mock.Mock(settled={}, matches={})
        snap.store.runs.return_value = []
        snap.store.predictions.return_value = []
        now = datetime.datetime(2026, 11, 11, 1, 30, tzinfo=datetime.timezone.utc)
        cases = {"rounding": (["94cff5deeace: recomputed 0.6499868570461047, stored 0.6499868570461048"], True, 0, 1),
                 "changed": (["94cff5deeace: recomputed 0.6499, stored 0.6500"], False, 1, 0),
                 "chain": (["chain broken at seq 5"], False, 1, 0)}
        for case, (found, ok, problems, notes) in cases.items():
            with self.subTest(case), mock.patch("matchup_dna.forecasting.api.verify_store", return_value=found), \
                    mock.patch("matchup_dna.forecasting.api.freshness",
                               return_value={"ok": True, "rule": "r", "forecast": {}, "settle": {}, "espn_download": {}}):
                status = views.status_view(snap, now)
                self.assertEqual((status["integrity"]["ok"], status["integrity"]["problems"],
                                  status["integrity"]["rounding_notes"]), (ok, problems, notes))

    def test_forecast_slot_due_once(self):
        g = self.gate

        class Store:
            def __init__(self, rows):
                self.db = sqlite3.connect(":memory:")
                self.db.row_factory = sqlite3.Row
                self.db.execute("CREATE TABLE runs (kind TEXT, started_at TEXT, status TEXT)")
                self.db.executemany("INSERT INTO runs VALUES (?, ?, 'ok')", rows)

        now = self.at("2026-11-10 12:40")                               # 07:40 Eastern
        self.assertTrue(g.forecast_due(Store([("forecast", "2026-11-10T00:03:00Z")]), now)[0])
        self.assertFalse(g.forecast_due(Store([("forecast", "2026-11-10T12:05:00Z")]), now)[0])   # already ran
        self.assertFalse(g.forecast_due(Store([]), self.at("2026-11-10 16:00"))[0])              # 11:00 Eastern: no slot
        self.assertFalse(g.forecast_due(Store([("settle", "2026-11-10T12:05:00Z"), ("forecast", "2026-11-10T12:01:00Z")]),
                                        now)[0])


class ReplacedPlayerTests(unittest.TestCase):
    """A result recorded under a match number the provider later reused for different players is not shown."""

    def snapshot(self, later_away_id, later_away_name):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.executescript(
            "CREATE TABLE source_records (record_id INTEGER PRIMARY KEY, provider TEXT, tour TEXT, provider_match_id TEXT,"
            " retrieved_at TEXT, payload_json TEXT);"
            "CREATE TABLE identity_observations (provider TEXT, tour TEXT, provider_player_id TEXT, player_id INTEGER,"
            " status TEXT, first_seen_at TEXT);")
        for espn, pid in (("1", 100), ("2", 200), ("3", 300)):
            db.execute("INSERT INTO identity_observations VALUES ('espn', 'ATP', ?, ?, 'verified', '2026-11-01')", (espn, pid))
        first = {"provider": "espn", "home_id": "2", "home_name": "Shevchenko", "away_id": "1", "away_name": "Van Assche"}
        later = dict(first, away_id=later_away_id, away_name=later_away_name, status="scheduled")   # as stored
        db.execute("INSERT INTO source_records VALUES (1, 'espn', 'ATP', '186526', '2026-11-08T20:00:00Z', ?)", (json.dumps(first),))
        db.execute("INSERT INTO source_records VALUES (2, 'espn', 'ATP', '186526', '2026-11-10T13:20:00Z', ?)", (json.dumps(later),))
        snap = views._Snapshot.__new__(views._Snapshot)
        snap.store = type("S", (), {"db": db})()
        snap.matches = {"M-1": {"tour": "ATP", "player_low": 100, "player_high": 200}}
        snap.records = {"M-1": first}
        snap.settled = {"M-1": {"state": "settled", "status": "completed", "winner_id": 200, "rows": [
            {"source": "espn", "provider_match_id": "186526", "retrieved_at": "2026-11-10T13:20:00Z", "score": "6-1 6-3"}]}}
        return snap

    def test_replaced_player_means_not_played(self):
        snap = self.snapshot("3", "Adrian Mannarino")
        note = "Not played: Van Assche was replaced by Adrian Mannarino. Shevchenko beat Mannarino 6-1 6-3."
        self.assertEqual(snap.replaced("M-1"), note)
        self.assertEqual(snap.result("M-1", [100, 200]),
                         {"status": "cancelled", "winner_index": None, "score": None, "note": note})
        self.assertEqual(snap.state("M-1", datetime.datetime(2026, 11, 10, tzinfo=datetime.timezone.utc)), "cancelled")

    def test_same_players_keep_their_result(self):
        snap = self.snapshot("1", "Van Assche")
        self.assertIsNone(snap.replaced("M-1"))
        self.assertEqual(snap.result("M-1", [100, 200])["winner_index"], 1)


class MatchStateTests(unittest.TestCase):
    def test_result_pending_from_the_start_until_settled(self):
        snap = views._Snapshot.__new__(views._Snapshot)
        snap.settled = {"M-done": {"state": "settled", "status": "completed"}}
        snap.matches = {}
        snap.records = {uid: {"event_time": "2026-11-09T12:00:00Z", **extra} for uid, extra in {
            "M-later": {}, "M-started": {}, "M-live": {"status": "in_progress"}, "M-done": {"status": "completed"},
            "M-rain": {"raw_status": "STATUS_SUSPENDED"}}.items()}
        snap.records["M-tbc"] = {}
        at = lambda hhmm: datetime.datetime(2026, 11, 9, int(hhmm[:2]), int(hhmm[2:]), tzinfo=datetime.timezone.utc)
        self.assertEqual(snap.state("M-later", at("1159")), "scheduled")
        self.assertEqual(snap.state("M-started", at("1200")), "result_pending")       # from the scheduled start
        self.assertEqual(snap.state("M-live", at("1130")), "result_pending")          # under way (early): still pending
        self.assertEqual(snap.state("M-done", at("1500")), "completed")
        self.assertEqual(snap.state("M-rain", at("1300")), "suspended")
        self.assertEqual(snap.state("M-tbc", at("1300")), "time_tbc")


class PilotExceptionTests(unittest.TestCase):
    def _files(self, tmp, issued="2026-11-08T19:23:32Z", players=(1, 2)):
        content = {"player_a": players[0], "player_b": players[1], "p_a": 0.52, "model_version": "ts-v1",
                   "issued_at": issued, "scheduled_start": "2026-11-08T21:30:00Z", "supersedes": None,
                   "input_sha256": "ab" * 32, "model_sha256": "cd" * 32}
        ledger = Path(tmp) / "pilot.jsonl"
        ledger.write_text(json.dumps({"prediction_id": "pid1", "seq": 1, "record_hash": "ef" * 32, "content": content}) + "\n")
        exceptions = Path(tmp) / "exceptions.json"
        exceptions.write_text(json.dumps({"matches": [{"match_uid": "M-1", "prediction_id": "pid1", "ledger": "pilot.jsonl"}]}))
        return exceptions

    def test_shown_only_when_every_check_passes(self):
        matches = {"M-1": {"player_low": 1, "player_high": 2}}
        records = {"M-1": {"event_time": "2026-11-08T22:05:00Z"}}
        with tempfile.TemporaryDirectory() as tmp:
            found = views.load_pilots(matches, records, {"ts-v1": "tournament_start"}, self._files(tmp), tmp)
            self.assertEqual(list(found), [("M-1", "ts-v1")])
            self.assertTrue(found[("M-1", "ts-v1")][0]["pilot"])
            for name, (m, r, kinds, files) in {
                "issued after the start": (matches, records, {"ts-v1": 1}, {"issued": "2026-11-08T22:10:00Z"}),
                "different players": (matches, records, {"ts-v1": 1}, {"players": (1, 3)}),
                "unknown model": (matches, records, {"other": 1}, {}),
                "unknown match": ({}, records, {"ts-v1": 1}, {}),
                "no start time": (matches, {}, {"ts-v1": 1}, {}),
            }.items():
                with self.subTest(name), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(views.load_pilots(m, r, kinds, self._files(tmp, **files), tmp), {})

    def test_never_counted_archived_or_in_player_views(self):
        snap = views._Snapshot.__new__(views._Snapshot)
        snap.predictions, snap.pilots = {}, {("M-1", "ts-v1"): [{"prediction_id": "pid1"}]}
        self.assertEqual(snap.rows("M-1", "ts-v1"), [{"prediction_id": "pid1"}])
        snap.predictions = {("M-1", "ts-v1"): [{"prediction_id": "real"}]}
        self.assertEqual(snap.rows("M-1", "ts-v1"), [{"prediction_id": "real"}])   # a stored forecast always wins
        source = Path(views.__file__).read_text(encoding="utf-8")
        for view in ("def counted", "def archive", "def players_view", "def track_record"):
            body = source.split(view, 1)[1].split("\ndef ", 1)[0]
            self.assertNotIn("pilot", body.replace("pilot_exceptions", ""), view)
            self.assertNotIn(".rows(", body, view)


class PruneTests(unittest.TestCase):
    def test_keeps_the_newest_snapshots_and_nothing_else_is_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stamps = [f"202611{d:02d}T073500Z" for d in range(1, 8)]
            for s in stamps:
                (root / s).mkdir()
            (root / "notes").mkdir()                                  # not a snapshot: left alone
            (root / "manifest.json").write_text("{}")
            publish.prune(root, current=stamps[-1], keep=3)
            self.assertEqual(sorted(p.name for p in root.iterdir()), sorted(stamps[-3:] + ["notes", "manifest.json"]))
            publish.prune(root, current=stamps[-1], keep=0)
            self.assertIn(stamps[-1], {p.name for p in root.iterdir()})    # the current snapshot is never deleted


class ContractTests(unittest.TestCase):
    def summary(self, **forecast):
        base = {"available": False, "model_version": "v", "decision": "deferred", "reason_code": "x", "reason": "r"}
        return {"state": "scheduled", "players": [{"id": 1}, {"id": 2}],
                "forecasts": {"round_aware": dict(base, **forecast)}}

    def test_unavailable_with_a_number_is_refused(self):
        with self.assertRaises(contract.ContractError):
            contract.check_match_summary(self.summary(p=[0.6, 0.4]), "$", {"v"})

    def test_probabilities_must_sum_to_one(self):
        bad = self.summary(available=True, p=[0.6, 0.5], revision=None, prediction_id="x", counted=True)
        with self.assertRaises(contract.ContractError):
            contract.check_match_summary(bad, "$", {"v"})

    def test_paths_and_private_fields_are_refused(self):
        for document in ({"note": "C:\\Users\\someone\\data"}, {"run_id": "forecast-1"}, {"issued_at": "2026-11-09"}):
            with self.assertRaises(contract.ContractError):
                contract.check_any(document)


class IsolationTests(unittest.TestCase):
    FORBIDDEN = {"matchup_dna.forecasting.engine", "matchup_dna.forecasting.pipeline",
                 "matchup_dna.forecasting.frozen_models", "matchup_dna.forecasting.history",
                 "matchup_dna.forecasting.espn", "matchup_dna.forecasting.providers"}

    def test_publisher_imports_no_forecasting_or_ingestion_code(self):
        for path in (ROOT / "web" / "publisher").glob("*.py"):
            if path.name == "players.py":
                continue            # checked separately below: it may use the job's read path, never its write path
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
                self.assertFalse(self.FORBIDDEN & set(names), f"{path.name} imports {self.FORBIDDEN & set(names)}")

    def test_players_export_uses_only_the_read_path(self):
        tree = ast.parse((ROOT / "web" / "publisher" / "players.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported |= {node.module} | {f"{node.module}.{a.name}" for a in node.names}
        for banned in ("matchup_dna.forecasting.engine", "matchup_dna.forecasting.frozen_models",
                       "matchup_dna.forecasting.pipeline.forecast", "matchup_dna.forecasting.pipeline.settle",
                       "matchup_dna.forecasting.store"):
            self.assertNotIn(banned, imported)

    def test_protected_code_still_matches_the_p1_protocol(self):
        """The protected code is the protocol's, or a committed amendment's (so this fails until an amendment and the
        code it describes are committed together)."""
        self.assertIn(prospective.code_sha256(), prospective.accepted_code(prospective.load_protocol()))


class PlayersExportTests(unittest.TestCase):
    """The all-players export on a tiny synthetic history (no files are read)."""

    def history(self):
        def m(date, tour, w, l, wn, ln, surface="Hard", rnd="R32"):
            return {"tour": tour, "tourney_date": date, "match_day": date, "winner_id": w, "loser_id": l,
                    "winner_name": wn, "loser_name": ln, "surface": surface, "round": rnd, "tourney_name": "Test Open",
                    "score": "6-4 6-4", "best_of": 3, "outcome": "completed", "winner_rank": 10, "loser_rank": 20}
        return [m(20260105, "ATP", 1, 2, "Ann Ace", "Bo Base"), m(20260112, "ATP", 1, 2, "Ann Ace", "Bo Base", "Clay"),
                m(20260119, "ATP", 2, 1, "Ann Ace", "Bo Base"),
                m(20200106, "ATP", 3, 2, "Cy Gone", "Bo Base")]           # player 3 has not played for years

    def test_profiles(self):
        import datetime as dt
        from types import SimpleNamespace
        from web.publisher import players
        history = self.history()
        history[2]["winner_name"], history[2]["loser_name"] = "Bo Base", "Ann Ace"
        now = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)
        index, profiles = players.build(history, SimpleNamespace(td_rows=[], td_links={}), now)
        self.assertEqual({p["id"] for p in index}, {1, 2})                # inactive player 3 is left out
        ann = profiles[("ATP", 1)]
        self.assertEqual(ann["season"]["All"], [2, 1])
        self.assertEqual(ann["season"]["Clay"], [1, 0])
        self.assertEqual(ann["recent"][0]["won"], False)                   # newest first
        self.assertEqual(ann["recent"][0]["opponent"], "Bo Base")
        self.assertEqual(index[0]["elo_rank"], 1)
        spark = next(p for p in index if p["id"] == 1)["spark"]
        self.assertEqual([d for d, _ in spark], sorted(d for d, _ in spark))   # dated, oldest first
        self.assertEqual(spark[-1][1], ann["elo"])                              # ends at the current rating
        self.assertTrue(ann["series"][-1][0].startswith("2026-03-01"))     # the trend ends today
        for doc in profiles.values():
            contract.check_any(doc)

    def test_head_to_head(self):
        import datetime as dt
        from types import SimpleNamespace
        from web.publisher import players
        history = self.history()
        retired = dict(history[0], tourney_date=20260126, match_day=20260127, outcome="retired", score="6-4 2-0 RET")
        walkover = dict(history[0], tourney_date=20260202, match_day=20260202, outcome="walkover", score="W/O")
        index, profiles = players.build(history + [retired, walkover], SimpleNamespace(td_rows=[], td_links={}),
                                        dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc))
        ann, bo = profiles[("ATP", 1)], profiles[("ATP", 2)]
        self.assertEqual(sorted(ann["h2h"]), ["2"])                        # inactive player 3 is not an opponent here
        meetings = ann["h2h"]["2"]
        self.assertEqual(len(meetings), 4)                                 # the walkover does not count
        self.assertEqual(meetings[0]["date"], "2026-01-27")                # newest first
        self.assertTrue(meetings[0]["retired"])
        self.assertEqual(sum(x["won"] for x in meetings), 3)
        self.assertEqual(sum(x["won"] for x in bo["h2h"]["1"]), 1)         # mirrored from the other side
        self.assertEqual([x["date"] for x in bo["h2h"]["1"]], [x["date"] for x in meetings])

    def test_retired_players_leave_the_tables_but_not_the_history(self):
        import datetime as dt
        from types import SimpleNamespace
        from web.publisher import players
        history = self.history()
        now = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)
        sources = SimpleNamespace(td_rows=[], td_links={})
        _, before = players.build(history, sources, now)
        index, profiles = players.build(history, sources, now, retired={("ATP", 2): "Bo Base"})
        self.assertEqual([p["id"] for p in index], [1])
        ann = profiles[("ATP", 1)]
        self.assertEqual(ann["elo"], before[("ATP", 1)]["elo"])           # their matches still count in the ratings
        self.assertEqual(ann["recent"][0]["opponent"], "Bo Base")         # and in other players' results
        self.assertEqual(ann["elo_rank"], 1)
        with self.assertRaises(ValueError):                                # a listing must name the right player
            players.build(history, sources, now, retired={("ATP", 2): "Someone Else"})

    def test_retired_list_is_sourced(self):
        from web.publisher import players
        doc = json.loads(players.RETIRED.read_text(encoding="utf-8"))
        for r in doc["players"]:
            self.assertIn(r["tour"], ("ATP", "WTA"))
            self.assertTrue(r["source"].startswith("https://"))
            self.assertRegex(r["retired"], r"^\d{4}-\d{2}$")

    def test_photos_only_for_verified_unique_identities(self):
        from types import SimpleNamespace
        from web.publisher.players import espn_photos
        verdicts = {"11": {"status": "verified", "player_id": 1}, "12": {"status": "ambiguous", "player_id": 2},
                    "13": {"status": "verified", "player_id": 3}, "14": {"status": "verified", "player_id": 3}}
        rec = lambda h, a: SimpleNamespace(provider="espn", tour="ATP", home_id=h, away_id=a, home_name="x", away_name="y")
        assembly = SimpleNamespace(resolvers={"espn": lambda tour, pid, name: verdicts.get(str(pid))},
                                   records=[rec("11", "12"), rec("13", "14")])
        photos = espn_photos(assembly)
        self.assertEqual(set(photos), {("ATP", 1)})                  # ambiguous id 12 and two ids for player 3: no photo
        self.assertIn("/full/11.png", photos[("ATP", 1)])

    def test_missing_headshots_are_dropped_and_cached(self):
        import datetime as dt
        from web.publisher.players import available
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "cache.json"
            calls = []
            def check(url):
                calls.append(url)
                return {"u1": True, "u2": False, "u3": None}[url]
            now = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
            kept = available({("ATP", 1): "u1", ("ATP", 2): "u2", ("ATP", 3): "u3"}, now, check, cache, pause=0)
            self.assertEqual(kept, {("ATP", 1): "u1"})
            kept_again = available({("ATP", 1): "u1", ("ATP", 2): "u2"}, now, check, cache, pause=0)
            self.assertEqual(kept_again, {("ATP", 1): "u1"})
            self.assertEqual(calls, ["u1", "u2", "u3"])           # the second run used the cache

    def test_thin_keeps_the_ends(self):
        from web.publisher.players import thin
        points = list(range(500))
        out = thin(points, 80)
        self.assertEqual(len(out), 80)
        self.assertEqual((out[0], out[-1]), (0, 499))


RESULTS_PRESENT = (ROOT / "results" / "phase5" / "evaluation" / "evaluation.json").exists()


@unittest.skipUnless(RESULTS_PRESENT, "research results are local files (gitignored)")
class ResearchExportTests(unittest.TestCase):
    def test_export_matches_the_reports_and_the_committed_files(self):
        from web.publisher import research
        historical, market = research.build()          # raises Mismatch if any headline differs from its report
        committed = ROOT / "web" / "content" / "research"
        self.assertEqual(json.loads((committed / "historical.json").read_text(encoding="utf-8")),
                         json.loads(json.dumps(historical, sort_keys=True)))
        self.assertEqual(json.loads((committed / "market.json").read_text(encoding="utf-8")),
                         json.loads(json.dumps(market, sort_keys=True)))

    def test_only_aggregates_leave(self):
        for name in ("historical.json", "market.json"):
            text = (ROOT / "web" / "content" / "research" / name).read_text(encoding="utf-8")
            for private in ("match_id", "a_id", "player_id", "a_name", "open_a", "close_a"):
                self.assertNotIn(private, text, f"{private} in {name}")

    def test_a_wrong_figure_is_refused(self):
        from web.publisher import research
        with self.assertRaises(research.Mismatch):
            research.same(0.6130, 0.6128, 4, "deliberately wrong")


if __name__ == "__main__":
    unittest.main()


class HeadshotTests(unittest.TestCase):
    """Official tour headshots: identity rules and the paced, cached lookups (no network)."""

    def test_atp_codes_through_the_crosswalk_one_to_one(self):
        from matchup_dna.merge import provider_only_id
        from web.publisher.headshots import atp_codes
        rows = [{"tour": "ATP", "winner_id": "S0AG", "loser_id": "A0E2"},
                {"tour": "ATP", "winner_id": "XX01", "loser_id": "XX02"},
                {"tour": "WTA", "winner_id": "123", "loser_id": "456"}]
        links = {("ATP", "S0AG"): 206173, ("ATP", "A0E2"): 207989, ("ATP", "XX01"): 1, ("ATP", "XX02"): 1}
        found = atp_codes(rows, links)
        self.assertEqual(found[("ATP", 206173)], "s0ag")
        self.assertEqual(found[("ATP", 207989)], "a0e2")
        self.assertNotIn(("ATP", 1), found)                                  # two codes for one player: dropped
        self.assertNotIn(("ATP", provider_only_id("tml", "WTA", "123")), found)

    def test_wta_matching_needs_a_unique_name_and_agreement(self):
        from web.publisher.headshots import match_wta
        people = {1: {"names": {"Cori Gauff", "Coco Gauff"}, "dob": "2004-03-13", "country": "USA"},
                  2: {"names": {"Ann Same"}, "dob": None, "country": "FRA"},
                  3: {"names": {"Bea Wrong"}, "dob": "2000-01-01", "country": "ESP"},
                  4: {"names": {"Cat Shared"}, "dob": None, "country": "ITA"},
                  5: {"names": {"Cat Shared"}, "dob": None, "country": "ITA"},
                  6: {"names": {"No Evidence"}, "dob": None, "country": None}}
        ranked = [{"id": 900, "fullName": "Coco Gauff", "countryCode": "USA", "dateOfBirth": "2004-03-13"},
                  {"id": 901, "fullName": "Ann Same", "countryCode": "FRA", "dateOfBirth": None},
                  {"id": 902, "fullName": "Bea Wrong", "countryCode": "ESP", "dateOfBirth": "2001-01-01"},
                  {"id": 903, "fullName": "Cat Shared", "countryCode": "ITA", "dateOfBirth": None},
                  {"id": 904, "fullName": "No Evidence", "countryCode": "GER", "dateOfBirth": None}]
        found = match_wta([1, 2, 3, 4, 6], people, ranked)
        self.assertEqual(found, {("WTA", 1): 900, ("WTA", 2): 901})          # alias name + birth date; name + country
        # 3: birth dates disagree; 4: another of our players has the name; 6: nothing to confirm the name with

    def test_official_rejects_the_silhouette_and_caches(self):
        import datetime as dt
        from web.publisher import headshots
        png = lambda tag: b"\x89PNG" + tag
        calls = []

        def get(url):
            calls.append(url)
            if "player-headshot/zzzz" in url:
                return 200, png(b"silhouette")
            if "player-headshot/s0ag" in url:
                return 200, png(b"sinner")
            if "player-headshot/nope" in url:
                return 200, png(b"silhouette")
            if "TENNIS_PLAYER%3A900" in url:
                return 200, json.dumps({"content": [{"onDemandUrl": "https://photoresources.wtatennis.com/a.jpg",
                                                     "references": [{"type": "TENNIS_PLAYER", "id": 900}]}]}).encode()
            return 200, json.dumps({"content": []}).encode()

        now = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "official.json"
            atp = {("ATP", 1): "s0ag", ("ATP", 2): "nope"}
            wta = {("WTA", 3): 900, ("WTA", 4): 901}
            found = headshots.official(atp, wta, now, get=get, cache_path=cache, pause=0)
            self.assertEqual(found, {("ATP", 1): headshots.ATP_IMAGE.format(code="s0ag"),
                                     ("WTA", 3): "https://photoresources.wtatennis.com/a.jpg" + headshots.WTA_SIZE})
            n = len(calls)
            self.assertEqual(headshots.official(atp, wta, now + dt.timedelta(days=1), get=get, cache_path=cache, pause=0), found)
            self.assertEqual(len(calls), n)                                  # answered from the cache within a week
            headshots.official(atp, wta, now + dt.timedelta(days=8), get=get, cache_path=cache, pause=0)
            self.assertGreater(len(calls), n)                                # re-checked after a week

    def test_commons_photos_through_wikidata_ids_with_credit(self):
        import datetime as dt
        import urllib.parse
        from web.publisher import headshots
        img = lambda f: {"type": "uri", "value": "http://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(f)}
        lit = lambda v: {"type": "literal", "value": v}
        item = lambda q: {"type": "uri", "value": "http://www.wikidata.org/entity/" + q}
        calls = []

        def get(url):
            calls.append(url)
            if url.startswith(headshots.WIKIDATA):
                query = urllib.parse.unquote(url)
                rows = []
                if "P536" in query:
                    rows = [{"item": item("Q1"), "id": lit("S0AG"), "image": img("Wide shot.jpg")},
                            {"item": item("Q1"), "id": lit("S0AG"), "image": img("Sinner (cropped).jpg")},
                            {"item": item("Q2"), "id": lit("D0CO"), "image": img("Twin a.jpg")},   # one code, two items
                            {"item": item("Q3"), "id": lit("D0CO"), "image": img("Twin b.jpg")},
                            {"item": item("Q4"), "id": lit("N0NE")}]                               # no image
                elif "P597" in query:
                    rows = [{"item": item("Q5"), "id": lit("900"), "image": img("Gauff.jpg")}]
                return 200, json.dumps({"results": {"bindings": rows}}).encode()
            info = lambda name, w, h, extra: {"imageinfo": [{
                "thumburl": f"https://upload.wikimedia.org/thumb/{name}/250px.jpg?utm_source=x", "width": w, "height": h,
                "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{name}", "extmetadata": extra}]}
            licensed = {"Artist": {"value": '<p><a href="//x">Jane &amp; Co</a>\n</p><ul><li>derivative work: Kim</li></ul>'}, "LicenseShortName": {"value": "CC BY-SA 4.0"},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"}}
            pages = {"1": dict(title="File:Wide shot.jpg", **info("Wide", 900, 600, licensed)),
                     "2": dict(title="File:Sinner (cropped).jpg", **info("Sinner", 600, 900, licensed)),
                     "3": dict(title="File:Gauff.jpg", **info("Gauff", 600, 800, {"Artist": {"value": "Unlicensed"}}))}
            return 200, json.dumps({"query": {"pages": pages}}).encode()

        now = dt.datetime(2026, 11, 9, tzinfo=dt.timezone.utc)
        ids = {("ATP", 1): "s0ag", ("ATP", 2): "d0co", ("ATP", 3): "n0ne", ("WTA", 4): 900}
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "commons.json"
            found = headshots.commons(ids, now, get=get, cache_path=cache, pause=0)
            self.assertEqual(set(found), {("ATP", 1)})       # ambiguous code, no image, and an unlicensed file: none
            self.assertEqual(found[("ATP", 1)]["url"], "https://upload.wikimedia.org/thumb/Sinner/250px.jpg")  # portrait wins
            self.assertEqual(found[("ATP", 1)]["credit"], {"author": "Jane & Co; derivative work: Kim", "license": "CC BY-SA 4.0",
                                                          "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
                                                          "source": "https://commons.wikimedia.org/wiki/File:Sinner"})
            n = len(calls)
            self.assertEqual(headshots.commons(ids, now + dt.timedelta(days=1), get=get, cache_path=cache, pause=0), found)
            self.assertEqual(len(calls), n)                  # answered from the cache within a week

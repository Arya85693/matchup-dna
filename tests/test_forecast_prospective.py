"""Phase 6 prospective evaluation: which forecasts count, hand-checkable metrics, the paired comparison, and the
guards around the protocol and the one final evaluation."""
import datetime
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from matchup_dna.forecasting import prospective
from matchup_dna.forecasting.records import UTC, canonical_json, sha256_text
from matchup_dna.forecasting.store import Store

ARTIFACT = '{"model_version": "m-1"}'
T0 = datetime.datetime(2026, 11, 9, 8, 0, tzinfo=UTC)


def prediction(uid, p, issued, start="2026-11-09T12:00:00Z", kind="tournament_start", version="m-1", a=1, b=2,
               features=None):
    features = features or {"x": p}
    row = {"a_elo_matches": 50, "b_elo_matches": 50, "surface_elo_probability": 0.5}
    return {"schema": 1, "mode": "live", "match_uid": uid, "model_version": version, "model_sha256": sha256_text(ARTIFACT),
            "model_kind": kind, "run_id": "r", "issued_at": issued, "scheduled_start": start, "player_a": a,
            "player_b": b, "p_a": p, "input_sha256": sha256_text(canonical_json(features)),
            "inputs": {"features": features, "row": row,
                       "players": {"a": {"rank": 10, "identity": "verified"}, "b": {"rank": 30, "identity": "verified"}},
                       "fixture": {"tour": "ATP", "surface": "Hard", "tourney_level": "A", "tourney_name": "T",
                                   "round": "R32", "tourney_date": 20261109, "edition_uid": "E", "best_of": 3}},
            "code_sha256": "code"}


def store_with(predictions, outcomes):
    store = Store(":memory:", mode="live")
    store.start_run("r", "forecast", T0, {})
    store.register_model("m-1", "tournament_start", ARTIFACT, sha256_text(ARTIFACT))
    store.ensure_edition("E", "ATP", "T", 20261109, "A", "Hard", T0)
    uids = {p["match_uid"] for p in predictions} | {o[0] for o in outcomes}
    for n, uid in enumerate(sorted(uids)):
        store.ensure_match(uid, "ATP", "E", f"R{n}", 1, 2, T0)
    for p in predictions:
        store.add_prediction(p)
    for uid, status, winner in outcomes:
        store.add_outcome(uid, "tml", "1", status, winner, "6-4 6-4", 3, T0, T0, "r")
    return store


class CountingTests(unittest.TestCase):
    def test_the_first_forecast_counts_and_a_late_one_never_does(self):
        store = store_with([prediction("M-1", 0.6, "2026-11-09T08:00:00Z"),
                            prediction("M-1", 0.7, "2026-11-09T10:00:00Z", features={"x": 2}),
                            prediction("M-2", 0.6, "2026-11-09T11:50:00Z")], [])
        first = prospective.counted_predictions(store)
        self.assertEqual(set(first), {("M-1", "m-1")})          # M-2 was issued 10 minutes before its start
        self.assertEqual(first[("M-1", "m-1")]["p_a"], 0.6)
        latest = prospective.counted_predictions(store, rule="latest")
        self.assertEqual(latest[("M-1", "m-1")]["p_a"], 0.7)

    def test_only_completed_settled_matches_are_scored(self):
        store = store_with([prediction(f"M-{n}", 0.6, "2026-11-09T08:00:00Z") for n in range(4)],
                           [("M-0", "completed", 1), ("M-1", "retired", 2), ("M-2", "walkover", 1)])
        rows, excluded = prospective.rows_by_kind(store)
        self.assertEqual(len(rows["tournament_start"]), 1)
        self.assertEqual(rows["tournament_start"][0]["y"], 1)
        self.assertEqual(excluded, {"not a completed match (retired)": 1, "not a completed match (walkover)": 1,
                                    "no result yet": 1})

    def test_the_outcome_is_scored_from_player_as_side(self):
        store = store_with([prediction("M-0", 0.8, "2026-11-09T08:00:00Z", a=2, b=1)], [("M-0", "completed", 1)])
        rows, _ = prospective.rows_by_kind(store)
        self.assertEqual(rows["tournament_start"][0]["y"], 0)


class MetricTests(unittest.TestCase):
    def rows(self, ps, ys, week="2026-11-09"):
        return [{"p": p, "y": y, "week": week, "match_uid": f"M{i}"} for i, (p, y) in enumerate(zip(ps, ys))]

    def test_log_loss_brier_and_accuracy_by_hand(self):
        m = prospective.metrics(self.rows([0.8, 0.4, 0.5], [1, 1, 0]))
        expected = -(math.log(0.8) + math.log(0.4) + math.log(0.5)) / 3
        self.assertAlmostEqual(m["log_loss"], expected, places=12)
        self.assertAlmostEqual(m["brier"], (0.04 + 0.36 + 0.25) / 3, places=12)
        self.assertAlmostEqual(m["accuracy"], (1 + 0 + 0.5) / 3, places=12)  # an exact 0.5 counts half

    def test_reliability_bins_and_ece(self):
        p = np.array([0.15, 0.15, 0.85, 0.85])
        y = np.array([0, 0, 1, 0])
        bins = prospective.reliability(p, y)
        self.assertEqual([(b["bin"], b["n"], b["observed"]) for b in bins], [("0.1-0.2", 2, 0.0), ("0.8-0.9", 2, 0.5)])
        self.assertAlmostEqual(prospective.expected_calibration_error(p, y), (2 * 0.15 + 2 * 0.35) / 4, places=12)

    def test_paired_gap_is_new_minus_old_on_shared_matches_only(self):
        old = self.rows([0.6, 0.6, 0.6], [1, 0, 1])
        new = self.rows([0.7, 0.5], [1, 0])
        gap = prospective.paired(new, old)
        expected = ((-math.log(0.7) + math.log(0.6)) + (-math.log(0.5) + math.log(0.4))) / 2
        self.assertEqual(gap["n"], 2)
        self.assertAlmostEqual(gap["gap"], expected, places=12)

    def test_weeks_are_the_clusters(self):
        self.assertEqual(prospective.week_of(20261111), "2026-11-09")
        self.assertEqual(prospective.week_of(20261109), "2026-11-09")


class ProtocolGuardTests(unittest.TestCase):
    def test_a_protocol_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protocol.json"
            path.write_text("{}", encoding="utf-8")
            with mock.patch.object(prospective, "PROTOCOL_PATH", path):
                with self.assertRaises(SystemExit):
                    prospective.freeze()
            self.assertEqual(path.read_text(encoding="utf-8"), "{}")

    def test_the_final_evaluation_waits_for_the_window_and_runs_once(self):
        protocol = {"frozen_at": "2026-11-08T20:00:00Z", "code_sha256": "code", "models": {},
                    "window": {"issued_from": "2026-11-08T20:00:00Z", "scheduled_up_to": prospective.WINDOW_END,
                               "final_evaluation_not_before": prospective.EARLIEST_FINAL}}
        store = store_with([], [])
        with tempfile.TemporaryDirectory() as directory:
            final_dir = Path(directory) / "final"
            with mock.patch.object(prospective, "load_protocol", return_value=protocol), \
                    mock.patch.object(prospective, "FINAL_DIR", final_dir):
                with self.assertRaises(SystemExit):
                    prospective.evaluate(store, final=True, now="2027-01-01T00:00:00Z")
                prospective.evaluate(store, final=True, now="2027-07-20T00:00:00Z")
                self.assertTrue((final_dir / "evaluation.txt").exists())
                with self.assertRaises(SystemExit):
                    prospective.evaluate(store, final=True, now="2027-07-21T00:00:00Z")

    def test_forecasts_from_other_code_or_before_the_freeze_are_not_counted(self):
        protocol = {"frozen_at": "2026-11-09T07:00:00Z", "code_sha256": "code",
                    "models": {"tournament_start": {"artifact_sha256": sha256_text(ARTIFACT)}},
                    "window": {"issued_from": "2026-11-09T07:00:00Z", "scheduled_up_to": prospective.WINDOW_END,
                               "final_evaluation_not_before": prospective.EARLIEST_FINAL}}
        before = prediction("M-0", 0.6, "2026-11-09T06:00:00Z")
        other_code = dict(prediction("M-1", 0.6, "2026-11-09T08:00:00Z"), code_sha256="changed")
        counted = prediction("M-2", 0.6, "2026-11-09T08:00:00Z")
        store = store_with([before, other_code, counted], [(f"M-{n}", "completed", 1) for n in range(3)])
        with mock.patch.object(prospective, "load_protocol", return_value=protocol):
            text = "\n".join(prospective.evaluate(store, now="2026-11-10T00:00:00Z"))
        self.assertIn("tournament_start (all counted): n 1 ", text)
        self.assertIn("excluded: issued by code other than the protocol's: 1", text)


class AmendmentTests(unittest.TestCase):
    """The code rule's committed amendment: one chain from the frozen code, counted only once committed unchanged."""
    PROTOCOL = {"frozen_at": "2026-11-09T07:00:00Z", "code_sha256": "code", "code_files": ["a.py", "b.py"],
                "models": {"tournament_start": {"artifact_sha256": sha256_text(ARTIFACT)}},
                "window": {"issued_from": "2026-11-09T07:00:00Z", "scheduled_up_to": prospective.WINDOW_END,
                           "final_evaluation_not_before": prospective.EARLIEST_FINAL}}

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.protocol_path = Path(self.directory.name) / "phase6_prospective_protocol.json"
        self.protocol_path.write_text(json.dumps(self.PROTOCOL), encoding="utf-8")
        patch = mock.patch.object(prospective, "PROTOCOL_PATH", self.protocol_path)
        patch.start()
        self.addCleanup(patch.stop)

    def write(self, number, previous, code, **changes):
        contents = {"amendment": number, "amends_sha256": prospective.file_sha256(self.protocol_path.read_bytes()),
                    "previous_code_sha256": previous, "code_sha256": code, "created_at": "2026-11-10T18:00:00Z",
                    "changed_files": ["a.py"], **changes}
        prospective.amendment_path(number).write_text(json.dumps(contents), encoding="utf-8")

    def test_amendments_form_one_chain_and_count_only_when_committed(self):
        yes = lambda path: True       # noqa: E731
        self.assertEqual(prospective.accepted_code(self.PROTOCOL, yes), ["code"])
        self.write(1, "code", "code-1")
        self.write(2, "code-1", "code-2")
        self.assertEqual(prospective.accepted_code(self.PROTOCOL, yes), ["code", "code-1", "code-2"])
        not_two = lambda path: not path.name.endswith("_2.json")     # noqa: E731
        self.assertEqual(prospective.accepted_code(self.PROTOCOL, not_two), ["code", "code-1"])
        self.assertEqual(prospective.accepted_code(self.PROTOCOL, lambda path: False), ["code"])
        self.write(2, "code", "code-2")                       # a branch from the frozen code, not the chain
        self.assertEqual(prospective.accepted_code(self.PROTOCOL, yes), ["code", "code-1"])
        self.write(1, "code", "code-1", amends_sha256="another protocol")
        self.assertEqual(prospective.accepted_code(self.PROTOCOL, yes), ["code"])

    def test_forecasts_from_amended_code_count_and_other_code_still_does_not(self):
        self.write(1, "code", "code-1")
        frozen = prediction("M-1", 0.6, "2026-11-09T08:00:00Z")
        amended = dict(prediction("M-2", 0.6, "2026-11-10T19:00:00Z", start="2026-11-11T12:00:00Z"), code_sha256="code-1")
        other = dict(prediction("M-3", 0.6, "2026-11-10T19:00:00Z", start="2026-11-11T12:00:00Z"), code_sha256="else")
        store = store_with([frozen, amended, other], [(f"M-{n}", "completed", 1) for n in (1, 2, 3)])
        with mock.patch.object(prospective, "load_protocol", return_value=self.PROTOCOL), \
                mock.patch.object(prospective, "committed", return_value=True):
            text = "\n".join(prospective.evaluate(store, now="2026-11-12T00:00:00Z"))
        self.assertIn("tournament_start (all counted): n 2 ", text)
        self.assertIn("excluded: issued by code other than the protocol's: 1", text)
        self.assertIn("Amendment 1 (2026-11-10T18:00:00Z): code code-1", text)

    def test_amend_lists_the_changed_files_and_never_overwrites(self):
        details = {key: f"{key} text" for key in prospective.AMENDMENT_DETAILS}
        protocol = dict(self.PROTOCOL, code_sha256=prospective.combine({"a.py": "1", "b.py": "2"}, ["a.py", "b.py"]))
        with mock.patch.object(prospective, "CODE_FILES", ("a.py", "b.py")), \
                mock.patch.object(prospective, "ROOT", Path(self.directory.name)), \
                mock.patch.object(prospective, "load_protocol", return_value=protocol), \
                mock.patch.object(prospective, "frozen_file_hashes", return_value={"a.py": "1", "b.py": "2"}), \
                mock.patch("builtins.print"):
            with mock.patch.object(prospective, "code_file_hashes", return_value={"a.py": "1", "b.py": "2"}):
                with self.assertRaises(SystemExit):                    # nothing changed
                    prospective.amend(details)
            with mock.patch.object(prospective, "code_file_hashes", return_value={"a.py": "1", "b.py": "3"}):
                with self.assertRaises(SystemExit):                    # a statement is missing
                    prospective.amend(dict(details, eligibility_unchanged=""))
                written = prospective.amend(details, now=datetime.datetime(2026, 11, 10, 18, 0, tzinfo=UTC))
                self.assertEqual((written["amendment"], written["changed_files"]), (1, ["b.py"]))
                self.assertEqual(written["previous_code_sha256"], protocol["code_sha256"])
                self.assertEqual(written["code_sha256"],
                                 prospective.combine({"a.py": "1", "b.py": "3"}, ["a.py", "b.py"]))
                before = prospective.amendment_path(1).read_text(encoding="utf-8")
                with self.assertRaises(SystemExit):                    # not committed yet: never overwritten
                    prospective.amend(details)
                self.assertEqual(prospective.amendment_path(1).read_text(encoding="utf-8"), before)

    def test_the_freeze_commit_reproduces_the_real_protocol_fingerprint(self):
        """The 'before' side of amendment 1: committed files plus the untracked profile settings give the frozen
        fingerprint exactly (skipped where the repository or the settings file is not available)."""
        real = prospective.ROOT / "experiments" / "phase6_prospective_protocol.json"
        settings = prospective.ROOT / "results" / "phase4" / "profile_settings.json"
        if prospective.git("rev-parse", "HEAD")[0] != 0 or not settings.exists():
            self.skipTest("needs the git repository and results/phase4/profile_settings.json")
        with mock.patch.object(prospective, "PROTOCOL_PATH", real):
            protocol = json.loads(real.read_text(encoding="utf-8"))
            hashes = prospective.frozen_file_hashes(protocol)
        self.assertEqual(prospective.combine(hashes, protocol["code_files"]), protocol["code_sha256"])


if __name__ == "__main__":
    unittest.main()

"""Phase 7 publisher tests. They build synthetic stores in temporary folders with the Phase 6 test scenario; no test
opens data/store/live.sqlite.

    python -m unittest discover -s web/publisher/tests -t .
"""
import ast
import datetime
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
        self.assertEqual(prospective.code_sha256(), prospective.load_protocol()["code_sha256"])


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

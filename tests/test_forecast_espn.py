"""Phase 6 ESPN source: parsing real-shaped scoreboard payloads, linking to the history without duplicates, and turning
the rest into history additions and fixtures."""
import datetime
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from matchup_dna.forecasting import espn
from matchup_dna.forecasting import records as rec
from matchup_dna.forecasting.history import Assembly, Sources
from test_heldout import sackmann_people

RETRIEVED = "2026-07-16T06:00:00Z"


def competitor(pid, name, side, winner=None, games=(), tiebreaks=(), rank=None):
    lines = [{"value": float(g), "winner": None} for g in games]
    for line, tb in zip(lines, tiebreaks):
        if tb is not None:
            line["tiebreak"] = tb
    found = {"id": str(pid), "homeAway": side, "order": 1 if side == "home" else 2, "linescores": lines,
             "athlete": {"displayName": name, "fullName": name}}
    if winner is not None:
        found["winner"] = winner
    if rank is not None:
        found["curatedRank"] = {"current": rank}
    return found


def competition(cid, round_name, date, home, away, status="STATUS_FINAL", time_valid=True):
    return {"id": str(cid), "date": date, "timeValid": time_valid, "tournamentId": 439,
            "round": {"displayName": round_name}, "status": {"type": {"name": status, "state": "post"}},
            "competitors": [home, away]}


def payload(competitions, event_id="439-2026", name="Plava Laguna Croatia Open Umag", slug="mens-singles",
            major=False):
    return {"events": [{"id": event_id, "name": name, "date": "2026-07-12T04:00Z", "major": major,
                        "groupings": [{"grouping": {"slug": slug}, "competitions": competitions}]}]}


def umag_payload(extra=()):
    """Umag on ESPN: two R32 results (also in the history), a first-round result ESPN alone has, and two fixtures."""
    return payload([
        competition(1, "Round 1", "2026-07-13T10:00Z", competitor(1, "Jannik Sinner", "home", True, (6, 6)),
                    competitor(2, "Alexander Zverev", "away", False, (3, 3))),
        competition(2, "Round 1", "2026-07-13T12:00Z", competitor(3, "Ziga Sesko", "home", False, (3, 3)),
                    competitor(4, "Daniel Merida Aguilar", "away", True, (6, 6))),
        competition(3, "Round 1", "2026-07-14T12:00Z", competitor(5, "Tomas Martin Etcheverry", "home", True, (7, 6),
                                                                  (7, None)),
                    competitor(6, "Boris Arias", "away", False, (6, 4), (4, None))),
        competition(4, "Round 2", "2026-07-16T12:00Z", competitor(1, "Jannik Sinner", "home", rank=1),
                    competitor(4, "Daniel Merida Aguilar", "away", rank=60), status="STATUS_SCHEDULED"),
        competition(5, "Round 2", "2026-07-16T05:00Z", competitor(5, "Tomas Martin Etcheverry", "home"),
                    competitor(7, "TBD", "away"), status="STATUS_SCHEDULED"),
        competition(6, "Quarterfinal", "2026-07-18T04:00Z", competitor(8, "TBD", "home"), competitor(9, "TBD", "away"),
                    status="STATUS_SCHEDULED"),
        competition(7, "Semifinal", "2026-07-19T04:00Z", competitor(8, "TBD", "home"), competitor(9, "TBD", "away"),
                    status="STATUS_SCHEDULED"),
        competition(8, "Final", "2026-07-20T04:00Z", competitor(8, "TBD", "home"), competitor(9, "TBD", "away"),
                    status="STATUS_SCHEDULED"),
        *extra])


def history_match(winner, wname, loser, lname, round_name, number, date=20260713, tourney="TML-2026-439"):
    blank = {f: None for f in ("ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced")}
    return {"tour": "ATP", "key": ("ATP", tourney, str(number), round_name), "tourney_id": tourney,
            "tourney_name": "Umag", "tourney_level": "A", "tourney_date": date, "match_num": str(number),
            "surface": "Clay", "round": round_name, "best_of": 3, "score": "6-3 6-3", "outcome": "completed",
            "winner_id": winner, "winner_name": wname, "winner_rank": None, "loser_id": loser, "loser_name": lname,
            "loser_rank": None, "minutes": None, "draw_size": "", "winner_entry": "", "loser_entry": "",
            "source": "tml", "stats": {"w": dict(blank), "l": dict(blank)}, "match_day": date}


def assembly_with(history):
    names, sackmann = sackmann_people()
    sources = Sources([], [], sackmann, names, {}, {}, [], {})
    return Assembly(sackmann + history, [], {}, None, None, {}, {}, {}), sources


UMAG_HISTORY = [history_match(206173, "Jannik Sinner", 100644, "Alexander Zverev", "R32", 1),
                history_match(210017, "Daniel Merida", 212949, "Ziga Sesko", "R32", 8)]


class ParseTests(unittest.TestCase):
    def test_rounds_count_back_from_the_quarterfinal(self):
        comps = [{"round": {"displayName": n}} for n in ("Round 1", "Round 2", "Round 3", "Round 4", "Quarterfinal",
                                                         "Semifinal", "Final", "Qualifying Final")]
        self.assertEqual(espn.round_map(comps)["Round 1"], "R128")
        self.assertEqual(espn.round_map(comps)["Round 4"], "R16")
        small = [{"round": {"displayName": n}} for n in ("Round 1", "Round 2", "Quarterfinal", "Group Stage")]
        self.assertEqual((espn.round_map(small)["Round 1"], espn.round_map(small)["Group Stage"]), ("R32", "RR"))

    def test_records_scores_times_and_skips(self):
        found = {r.provider_match_id: r for r in espn.parse(umag_payload(), RETRIEVED)}
        self.assertEqual(set(found), {"1", "2", "3", "4"})      # TBD players skipped
        self.assertEqual((found["1"].round, found["1"].status, found["1"].score), ("R32", rec.COMPLETED, "6-3 6-3"))
        self.assertEqual(found["3"].score, "7-6(4) 6-4")         # the loser's tiebreak points
        self.assertEqual((found["4"].status, found["4"].event_time), (rec.SCHEDULED, "2026-07-16T12:00:00Z"))
        # ESPN's "curatedRank" is the tournament seed: kept as the seed, never read as a ranking
        self.assertEqual((found["4"].home_rank, found["4"].extra["home_seed"]), (None, 1))
        walkover = espn.parse(payload([competition(9, "Round 1", "2026-07-13T10:00Z",
                                                   competitor(1, "A B", "home", True), competitor(2, "C D", "away", False),
                                                   status="STATUS_WALKOVER")]), RETRIEVED)[0]
        self.assertEqual((walkover.status, walkover.score), (rec.WALKOVER, "W/O"))

    def test_a_placeholder_time_is_not_a_start_time(self):
        record = espn.parse(payload([competition(9, "Round 1", "2026-07-16T05:00Z", competitor(1, "A B", "home"),
                                                 competitor(2, "C D", "away"), status="STATUS_SCHEDULED",
                                                 time_valid=False)]), RETRIEVED)[0]
        self.assertIsNone(record.event_time)
        self.assertEqual(espn.day_of(record), datetime.date(2026, 7, 16))

    def test_the_womens_draw_of_a_joint_event_is_wta_and_read_once(self):
        both = umag_payload()
        both["events"][0]["groupings"].append({"grouping": {"slug": "womens-singles"}, "competitions": [
            competition(50, "Round 1", "2026-07-13T10:00Z", competitor(11, "Iga Swiatek", "home", True, (6, 6)),
                        competitor(12, "Coco Gauff", "away", False, (1, 1)))]})
        found = {r.provider_match_id: r.tour for r in espn.parse(both, RETRIEVED)}
        self.assertEqual(found["50"], "WTA")
        self.assertEqual(found["1"], "ATP")


class LinkTests(unittest.TestCase):
    def test_names_fit(self):
        self.assertTrue(espn.names_fit("Daniel Merida Aguilar", "Daniel Merida"))
        self.assertTrue(espn.names_fit("Daniel Merida Aguilar", "Merida Aguilar D."))
        # Erratum 1's Vallejo: a two-token name inside a three-token one fits, so linking alone cannot tell these two
        # apart; it is the unique-candidate rule and the identity checks that keep them separate.
        self.assertTrue(espn.names_fit("Daniel Vallejo", "Adolfo Daniel Vallejo"))
        self.assertFalse(espn.names_fit("Alexander Zverev", "Mischa Zverev"))
        self.assertFalse(espn.names_fit("Sinner", "Jannik Sinner"))  # one token is not enough

    def test_history_matches_link_once_and_teach_identities_and_the_edition(self):
        records = espn.parse(umag_payload(), RETRIEVED)
        links = espn.link(records, UMAG_HISTORY, 20260101)
        self.assertEqual(sorted(r.provider_match_id for r, _, _ in links), ["1", "2"])
        evidence = espn.Evidence(links)
        self.assertEqual(evidence.player("ATP", "4"), (210017, "consistent"))
        self.assertEqual(evidence.edition("ATP", "439-2026"), ("TML-2026-439", 20260713))
        self.assertEqual(evidence.tournament("ATP", "439"), ("A", "Clay"))


class IntegrateTests(unittest.TestCase):
    def integrate(self, history, extra=()):
        assembly, sources = assembly_with(list(history))
        return espn.integrate(assembly, sources, espn.parse(umag_payload(extra), RETRIEVED))

    def test_only_the_missing_result_is_added_and_fixtures_join_the_edition(self):
        assembly = self.integrate(UMAG_HISTORY)
        added = [m for m in assembly.matches if m["source"] == "espn"]
        self.assertEqual([(m["winner_name"], m["round"], m["tourney_id"]) for m in added],
                         [("Tomas Martin Etcheverry", "R32", "TML-2026-439")])
        self.assertEqual(added[0]["winner_id"], 144869)      # unique exact name in the Sackmann history
        fixture = assembly.fixtures[0]
        self.assertEqual((fixture["round"], fixture["status"], fixture["tourney_id"], fixture["surface"]),
                         ("R16", "pending", "TML-2026-439", "Clay"))
        self.assertEqual({fixture["home"]["player_id"], fixture["away"]["player_id"]}, {206173, 210017})
        self.assertEqual(fixture["away"]["status"], "verified")

    def test_fixture_ranks_are_the_latest_history_ranks_never_the_seed(self):
        ranked = [dict(m) for m in UMAG_HISTORY]
        ranked[0].update(winner_rank=2, loser_rank=3, match_day=20260713)     # Sinner's latest printed rank
        older = history_match(206173, "Jannik Sinner", 212949, "Ziga Sesko", "R16", 30, date=20260601)
        older.update(winner_rank=9, loser_rank=50, match_day=20260601)
        fixture = self.integrate(ranked + [older]).fixtures[0]
        people = {fixture[s]["player_id"]: fixture[s] for s in ("home", "away")}
        self.assertEqual((people[206173]["rank"], people[206173]["rank_as_of"], people[206173]["seed"]), (2, 20260713, 1))
        self.assertIsNone(people[210017]["rank"])   # no printed rank in the history: unranked, not seed 60

    def test_a_result_resembling_a_history_match_is_held_back_not_added(self):
        """The history spells Etcheverry's opponent differently and resolves him to another id: the ESPN row could be the
        same match, so it is never added on top."""
        history = UMAG_HISTORY + [history_match(144869, "Tomas Etcheverry Martin", 106262, "Boris Arias", "R32", 9)]
        history[-1]["winner_name"] = "Tomas Martin Etcheverry"
        assembly = self.integrate(history)
        self.assertEqual([m for m in assembly.matches if m["source"] == "espn"], [])

    def test_a_scheduled_match_the_history_already_has_is_already_played(self):
        played = history_match(206173, "Jannik Sinner", 210017, "Daniel Merida", "R16", 20, date=20260713)
        assembly = self.integrate(UMAG_HISTORY + [played])
        self.assertEqual(assembly.fixtures[0]["status"], "already_played")

    def test_who_is_still_playing_is_worked_out_again_with_the_results_espn_adds(self):
        """Amendment 1 to P1 (Paris 2026): TML's ongoing file stopped after the first round, so from TML alone Sinner
        and Merida were both still in the draw. ESPN has Merida's later loss, and then the final: the answer from TML
        alone must not survive either."""
        from matchup_dna.forecasting.history import still_playing
        later = [competition(1, "Round 1", "2026-07-13T10:00Z", competitor(1, "Jannik Sinner", "home", True, (6, 6)),
                             competitor(2, "Alexander Zverev", "away", False, (3, 3))),
                 competition(2, "Round 1", "2026-07-13T12:00Z", competitor(3, "Ziga Sesko", "home", False, (3, 3)),
                             competitor(4, "Daniel Merida Aguilar", "away", True, (6, 6))),
                 competition(10, "Round 2", "2026-07-15T12:00Z", competitor(1, "Jannik Sinner", "home", True, (6, 6)),
                             competitor(4, "Daniel Merida Aguilar", "away", False, (2, 2))),
                 competition(6, "Quarterfinal", "2026-07-18T04:00Z", competitor(8, "TBD", "home"),
                             competitor(9, "TBD", "away"), status="STATUS_SCHEDULED")]
        final = competition(11, "Final", "2026-07-20T12:00Z", competitor(1, "Jannik Sinner", "home", True, (6, 6)),
                            competitor(2, "Alexander Zverev", "away", False, (4, 4)))
        ongoing = {("ATP", "TML-2026-439")}
        for competitions, expected in ((later, {("ATP", 206173)}), (later + [final], set())):
            assembly, sources = assembly_with(list(UMAG_HISTORY))
            assembly.ongoing_editions = set(ongoing)
            assembly.still_playing = still_playing(assembly.matches, ongoing)
            self.assertEqual(set(assembly.still_playing), {("ATP", 206173), ("ATP", 210017)})   # TML alone
            espn.integrate(assembly, sources, espn.parse(payload(competitions), RETRIEVED))
            self.assertEqual(set(assembly.still_playing), expected)

    def test_tennisdata_challenger_rows_supply_ranks_for_crosswalked_players_before_the_day_only(self):
        from test_heldout import td_row
        names, sackmann = sackmann_people()
        challenger = td_row(70, "2026-07-10", "Merida Aguilar D.", "122001", "Nobody X.", "5", tour_type="3")
        challenger.update(home_rank="140", away_rank="300")
        later = td_row(71, "2026-07-20", "Merida Aguilar D.", "122001", "Nobody X.", "5", tour_type="3")
        later.update(home_rank="90")
        sources = Sources([], [challenger, later], sackmann, names, {}, {("ATP", "122001"): 210017}, [], {})
        ranks = espn.add_tennisdata_ranks({}, sources)
        self.assertEqual(espn.rank_before(ranks, "ATP", 210017, 20260716), (140, 20260710))
        self.assertNotIn(("ATP", 5), ranks)   # not in the validated crosswalk: never guessed

    def test_a_reviewed_alias_verifies_and_a_contradicted_one_is_a_conflict(self):
        assembly, sources = assembly_with(list(UMAG_HISTORY))
        people = espn.EspnIdentities(espn.Evidence(espn.link(espn.parse(umag_payload(), RETRIEVED), UMAG_HISTORY,
                                                             20260101)), assembly, sources,
                                     aliases={("ATP", "77"): 106262, ("ATP", "4"): 999})
        self.assertEqual(people.resolve("ATP", "77", "Bobby Arias-Smith"),
                         {"player_id": 106262, "status": "verified", "method": "reviewed alias"})
        self.assertEqual(people.resolve("ATP", "4", "Daniel Merida Aguilar")["status"], "conflict")

    def test_events_with_no_main_tour_evidence_are_left_out(self):
        assembly, sources = assembly_with([])  # nothing links: no evidence that Umag is a tour event
        espn.integrate(assembly, sources, espn.parse(umag_payload(), RETRIEVED))
        self.assertEqual(assembly.fixtures, [])
        self.assertEqual([m for m in assembly.matches if m["source"] == "espn"], [])


class ArchiveTests(unittest.TestCase):
    def test_the_archive_is_read_by_hash_and_by_retrieval_time(self):
        with tempfile.TemporaryDirectory() as directory:
            def response(body, retrieved, status=200):
                class Response:
                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        return False

                    def read(self):
                        return body
                Response.status = status
                return lambda request, timeout: Response()
            body = json.dumps(umag_payload()).encode()
            meta = espn.fetch("atp", datetime.date(2026, 7, 16), directory, opener=response(body, RETRIEVED))
            self.assertEqual(meta["body_sha256"], hashlib.sha256(body).hexdigest())
            first = espn.load_archive(directory)
            self.assertEqual(len(first), 4)
            self.assertEqual(espn.load_archive(directory), first)          # second read comes from the parse cache
            self.assertEqual(espn.load_archive(directory, as_of="2026-01-01T00:00:00Z"), [])
            # A later response for the same day wins: the R16 is now finished.
            later = umag_payload()
            r16 = later["events"][0]["groupings"][0]["competitions"][3]
            r16["status"]["type"]["name"] = "STATUS_FINAL"
            r16["competitors"][0].update(winner=True, linescores=[{"value": 6.0}, {"value": 6.0}])
            r16["competitors"][1].update(winner=False, linescores=[{"value": 2.0}, {"value": 2.0}])
            import time
            time.sleep(1.1)  # retrieval times are to the second
            meta = espn.fetch("atp", datetime.date(2026, 7, 16), directory,
                              opener=response(json.dumps(later).encode(), None))
            statuses = {r.provider_match_id: r.status for r in espn.load_archive(directory)}
            self.assertEqual(statuses["4"], rec.COMPLETED)
            (Path(directory) / meta["file"]).write_bytes(body + b" ")
            with self.assertRaises(ValueError):
                espn.load_archive(directory)


if __name__ == "__main__":
    unittest.main()

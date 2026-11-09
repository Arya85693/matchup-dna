"""Phase 6 history and fixtures: one record per real match and one identity per real player, while tournaments are
still running. Synthetic TML and TennisData.app rows in the shapes the readers return (the erratum 1 test helpers)."""
import datetime
import unittest
from collections import Counter

from matchup_dna import heldout
from matchup_dna.forecasting import history
from matchup_dna.forecasting.history import Sources, assemble
from test_heldout import START, SNAPSHOT, sackmann_people, td_row, tml, umag

STAMP = {"test.csv": "2026-07-14T06:00:00Z", "2026_atp.csv": "2026-07-15T20:00:00Z"}


def scheduled(row):
    """A TD row as a scheduled fixture: no result yet."""
    row = dict(row, status="SCHEDULED", status_extra="SCHEDULED", winner_code="")
    for side in ("home", "away"):
        row[f"{side}_set_score"] = ""
        for n in range(1, 6):
            row[f"{side}_set_{n}_score"] = ""
    return row


def sources(tml_rows, td_rows, tml_links, td_links, people=None):
    names, sackmann = sackmann_people(people) if people else sackmann_people()
    return Sources(tml_rows, td_rows, sackmann, names, tml_links, td_links, [], dict(STAMP))


def fixture_named(assembly, name):
    return next(f for f in assembly.fixtures if name in (f["home"]["name"], f["away"]["name"]))


class SameAsResearchTests(unittest.TestCase):
    def test_finished_editions_assemble_exactly_as_the_corrected_research_assembly(self):
        tml_rows, td_rows, tml_links, td_links = umag()
        found = assemble(sources(tml_rows, td_rows, tml_links, td_links))
        names, sackmann = sackmann_people()
        research, _, _ = heldout.assemble(tml_rows, td_rows, sackmann, names, tml_links, td_links, [], START,
                                          20261105, SNAPSHOT, version=2)
        provider = [m for m in found.matches if m["tourney_date"] >= START]
        strip = lambda m: {k: v for k, v in m.items() if k not in ("match_day", "provider_match_id", "source_file")}
        self.assertEqual(sorted(map(str, map(strip, provider))), sorted(map(str, map(strip, research))))
        self.assertEqual(Counter(m["source"] for m in provider), {"tml": 4})

    def test_ongoing_editions_are_kept(self):
        tml_rows, td_rows, tml_links, td_links = umag()
        for row in tml_rows:
            row["ongoing"] = True
        found = assemble(sources(tml_rows, td_rows, tml_links, td_links))
        self.assertEqual(len([m for m in found.matches if m["tourney_date"] >= START]), 4)


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.tml_rows, self.td_rows, self.tml_links, self.td_links = umag()

    def run_with(self, extra_td, extra_tml=()):
        return assemble(sources(self.tml_rows + list(extra_tml), self.td_rows + list(extra_td), self.tml_links,
                                self.td_links))

    def test_a_fixture_joins_its_edition_and_players_resolve_through_the_linked_providers(self):
        found = self.run_with([scheduled(td_row(10, "2026-07-17", "Sinner J.", "206173", "Merida Aguilar D.", "122001",
                                                round_name="QF"))])
        fixture = fixture_named(found, "Sinner J.")
        self.assertEqual(fixture["status"], "pending")
        self.assertEqual(fixture["tourney_id"], "TML-2026-439")  # the TML edition holding the earlier rounds
        self.assertEqual(fixture["tourney_date"], 20260713)
        self.assertEqual((fixture["home"]["player_id"], fixture["home"]["status"]), (206173, "verified"))
        self.assertEqual((fixture["away"]["player_id"], fixture["away"]["status"]), (210017, "verified"))

    def test_a_fixture_another_source_already_reports_as_played_is_never_forecast(self):
        played = tml(20260717, "Jannik Sinner", "S0AG", "Daniel Merida", "M0N7", number="20", round_name="QF")
        found = self.run_with([scheduled(td_row(10, "2026-07-17", "Sinner J.", "206173", "Merida Aguilar D.", "122001",
                                                round_name="QF"))], [played])
        self.assertEqual(fixture_named(found, "Sinner J.")["status"], "already_played")

    def test_last_weeks_meeting_does_not_make_this_weeks_fixture_look_played(self):
        """Sesko and Etcheverry met in the Kitzbuhel R32 (TML, 21 July). A scheduled R32 fixture between them in the
        next event, six days later, is a different match. The research linking (names and a -3 to +16 day window)
        would have tied it to the Kitzbuhel row; a scheduled row is never linked that way."""
        later = scheduled(td_row(11, "2026-07-27", "Sesko Z.", "212949", "Etcheverry T. M.", "144869",
                                 tournament="Gstaad ATP", round_name="R32"))
        found = self.run_with([later])
        self.assertEqual(fixture_named(found, "Sesko Z.")["status"], "pending")
        kitzbuhel = [r for r in self.tml_rows if r["tourney_name"] == "Kitzbuhel"]
        from matchup_dna.audit_tennisismylife import td_to_tml
        self.assertEqual(td_to_tml([later], kitzbuhel)[0]["status"], "linked")  # what the research pass would do

    def test_the_same_fixture_listed_twice_is_one_fixture(self):
        row = td_row(10, "2026-07-17", "Sinner J.", "206173", "Merida Aguilar D.", "122001", round_name="QF")
        found = self.run_with([scheduled(row), scheduled(dict(row, match_id="12"))])
        statuses = sorted(f["status"] for f in found.fixtures)
        self.assertEqual(statuses, ["duplicate", "pending"])


class IdentityTests(unittest.TestCase):
    def test_a_crosswalk_that_disagrees_with_the_linked_tml_player_is_a_conflict(self):
        """The Vallejo case: TennisData.app's crosswalk names Daniel Vallejo (118808); the linked TML player is
        Adolfo Daniel Vallejo (209226). The history uses the TML identity; the fixture is held back for review."""
        tml_rows = [tml(20260713, "Adolfo Daniel Vallejo", "V0DP", "Boris Arias", "A0BB", number="1")]
        td_rows = [td_row(1, "2026-07-13", "Vallejo D.", "424916", "Arias B.", "106262")]
        tml_links = {("ATP", "V0DP"): 209226, ("ATP", "A0BB"): 106262}
        td_links = {("ATP", "424916"): 118808, ("ATP", "106262"): 106262}
        fixture = scheduled(td_row(5, "2026-07-15", "Vallejo D.", "424916", "Arias B.", "106262", round_name="R16"))
        found = assemble(sources(tml_rows, td_rows + [fixture], tml_links, td_links))
        person = fixture_named(found, "Vallejo D.")["home"]
        self.assertEqual(person["player_id"], 209226)
        self.assertEqual(person["status"], "conflict")
        self.assertEqual({m["winner_id"] for m in found.matches if m["tourney_date"] >= START}, {209226})

    def test_an_unlinked_player_resembling_an_existing_one_is_ambiguous(self):
        """Erratum 1's split identities: a provider-only id whose name fits an active Sackmann player must not start a
        history-less player."""
        tml_rows, td_rows, tml_links, td_links = umag()
        fixture = scheduled(td_row(20, "2026-07-16", "Merida D.", "999001", "Sinner J.", "206173", round_name="QF"))
        found = assemble(sources(tml_rows, td_rows + [fixture], tml_links, td_links))
        person = fixture_named(found, "Merida D.")["home"]
        self.assertLess(person["player_id"], 0)
        self.assertEqual(person["status"], "ambiguous")

    def test_a_genuinely_new_player_is_forecastable(self):
        tml_rows, td_rows, tml_links, td_links = umag()
        fixture = scheduled(td_row(21, "2026-07-16", "Qwertyuiop Z.", "999002", "Sinner J.", "206173",
                                   round_name="QF"))
        found = assemble(sources(tml_rows, td_rows + [fixture], tml_links, td_links))
        self.assertEqual(fixture_named(found, "Qwertyuiop Z.")["home"]["status"], "new_player")

    def test_a_review_can_confirm_but_never_change_an_identity(self):
        fixtures = [{"tour": "ATP", "provider": "tennisdata_app",
                     "home": {"provider_id": "424916", "player_id": 209226, "status": "conflict", "method": "m"},
                     "away": {"provider_id": "1", "player_id": 5, "status": "ambiguous", "method": "m"}}]
        history.apply_reviews(fixtures, {("ATP", "tennisdata_app", "424916"): 209226,
                                         ("ATP", "tennisdata_app", "1"): 6})
        self.assertEqual(fixtures[0]["home"]["status"], "verified")
        self.assertEqual((fixtures[0]["away"]["status"], fixtures[0]["away"]["player_id"]), ("ambiguous", 5))


class StillPlayingTests(unittest.TestCase):
    def test_players_alive_in_an_ongoing_edition_without_a_final(self):
        matches = [{"tour": "ATP", "tourney_id": "TML-1", "tourney_date": 20260713, "round": "R32", "winner_id": 1,
                    "loser_id": 2}, {"tour": "ATP", "tourney_id": "TML-1", "tourney_date": 20260713, "round": "R16",
                                     "winner_id": 3, "loser_id": 1}]
        alive = history.still_playing(matches, {("ATP", "TML-1")})
        self.assertEqual(set(alive), {("ATP", 3)})
        finished = matches + [{"tour": "ATP", "tourney_id": "TML-1", "tourney_date": 20260713, "round": "F",
                               "winner_id": 3, "loser_id": 9}]
        self.assertEqual(history.still_playing(finished, {("ATP", "TML-1")}), {})


if __name__ == "__main__":
    unittest.main()

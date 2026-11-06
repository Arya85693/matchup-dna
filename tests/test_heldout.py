"""Phase 4 erratum 1: the held-out provider assembly (heldout.assemble version 2) and its regression cases.

Synthetic rows only, except RealHeldOutTests, which runs when the private provider files are present and uses the
sealed (outcome-free) rows.
"""
import copy
import datetime
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from matchup_dna import heldout
from matchup_dna.crosswalk import sackmann_name_keys
from matchup_dna.merge import provider_only_id, tml_match
from test_round_aware import match as sackmann_match
from test_tennisdata import loaded, provider_row
from test_tennisismylife import tml_row

START, END = 20260601, 20261105
SNAPSHOT = datetime.date(2026, 11, 5)
ROUND_NAMES = {"R128": "1/64-finals", "R64": "1/32-finals", "R32": "1/16-finals", "R16": "1/8-finals",
               "QF": "Quarter-finals", "SF": "Semi-finals", "F": "Final", "": ""}
STAT_LINE = {"ace": "5", "df": "2", "svpt": "60", "1stIn": "36", "1stWon": "28", "2ndWon": "12", "SvGms": "10",
             "bpSaved": "2", "bpFaced": "3"}


def td_row(match_id, day, home, home_id, away, away_id, tournament="Umag ATP", round_name="R32", winner="1",
           tour_type="1"):
    """A TennisData.app row as load_provider returns it (open, with its result)."""
    stamp = int(datetime.datetime.fromisoformat(day).replace(hour=12, tzinfo=datetime.timezone.utc).timestamp())
    games = {"1": ("6", "3"), "2": ("3", "6")}[winner]
    row = provider_row(match_id, stamp, tournament=tournament, tour_type=tour_type, round=ROUND_NAMES[round_name],
                       home_name=home, home_id=home_id, away_name=away, away_id=away_id, winner_code=winner,
                       home_set_1_score=games[0], away_set_1_score=games[1], home_set_2_score=games[0],
                       away_set_2_score=games[1], home_set_score="2" if winner == "1" else "0",
                       away_set_score="0" if winner == "1" else "2")
    return loaded(row)


def tml(date, winner, winner_id, loser, loser_id, tourney_id="2026-439", number="1", round_name="R32",
        name="Umag", tour="ATP"):
    """A TML row as load_tml returns it for an unlocked held-out match."""
    row = tml_row(date, winner_id=winner_id, loser_id=loser_id, tourney_id=tourney_id, match_num=number,
                  winner_name=winner, loser_name=loser, round=round_name, tourney_name=name, tourney_level="250",
                  surface="Clay", **{f"{p}_{f}": v for p in ("w", "l") for f, v in STAT_LINE.items()})
    row.update(tour=tour, sealed=True, ongoing=False, source_file=f"2026_{tour.lower()}.csv")
    return row


PEOPLE = {210017: ("Daniel", "Merida Aguilar"), 212949: ("Ziga", "Sesko"), 144869: ("Tomas Martin", "Etcheverry"),
          206173: ("Jannik", "Sinner"), 100644: ("Alexander", "Zverev"), 209226: ("Adolfo Daniel", "Vallejo"),
          118808: ("Daniel", "Vallejo"), 106262: ("Boris", "Arias"), 126203: ("Taylor", "Fritz"),
          126205: ("Tommy", "Paul")}


def sackmann_people(ids=PEOPLE):
    names = {("ATP", i): {"first": f, "last": l, "keys": sackmann_name_keys(f, l)} for i, (f, l) in ids.items()}
    history = [sackmann_match(i, 999999, "R32", n, date=20250106 + 100 * n, tourney=f"H{n}")
               for n, i in enumerate(sorted(ids))]  # one match each, January to October 2025
    return names, history


def assemble(tml_rows, td_rows, tml_links, td_links, version=2, people=PEOPLE):
    names, history = sackmann_people(people)
    return heldout.assemble(tml_rows, td_rows, history, names, tml_links, td_links, [], START, END, SNAPSHOT,
                            version=version)


def umag():
    """Umag: Daniel Merida's two matches appear in both providers under different spellings; one ordinary match
    links by name keys. Kitzbuhel, a week later, is in TML only."""
    tml_rows = [
        tml(20260713, "Jannik Sinner", "S0AG", "Alexander Zverev", "Z355", number="1"),
        tml(20260713, "Daniel Merida", "M0N7", "Ziga Sesko", "S0AB", number="8"),
        tml(20260715, "Daniel Merida", "M0N7", "Tomas Martin Etcheverry", "E0CD", number="16", round_name="R16"),
        tml(20260721, "Ziga Sesko", "S0AB", "Tomas Martin Etcheverry", "E0CD", tourney_id="2026-319",
            name="Kitzbuhel"),
    ]
    td_rows = [
        td_row(1, "2026-07-13", "Sinner J.", "206173", "Zverev A.", "100644"),
        td_row(2, "2026-07-13", "Sesko Z.", "212949", "Merida Aguilar D.", "122001", winner="2"),
        td_row(3, "2026-07-15", "Etcheverry T. M.", "144869", "Merida Aguilar D.", "122001", round_name="R16",
               winner="2"),
    ]
    tml_links = {("ATP", "S0AG"): 206173, ("ATP", "Z355"): 100644, ("ATP", "S0AB"): 212949, ("ATP", "E0CD"): 144869}
    td_links = {("ATP", "206173"): 206173, ("ATP", "100644"): 100644, ("ATP", "212949"): 212949,
                ("ATP", "144869"): 144869, ("ATP", "122001"): 210017}
    return tml_rows, td_rows, tml_links, td_links


class NameRuleTests(unittest.TestCase):
    def test_alternate_spellings_and_abbreviations_are_compatible(self):
        for td_name, full in (("Merida Aguilar D.", "Daniel Merida"), ("Ruse G.", "Elena Gabriela Ruse"),
                              ("Vallejo D.", "Adolfo Daniel Vallejo"), ("Tam Sin Hang", "Sin Hang Tam"),
                              ("Choi W. F.", "Fu Wang Choi"), ("Wu Tung-Lin", "Tung-Lin Wu"),
                              ("Bassols M.", "Marina Bassols Ribera"), ("Struff J-L.", "Jan-Lennard Struff"),
                              ("Wu Y.", "Yibing Wu"), ("Carreno Busta P.", "Pablo Carreño Busta")):
            self.assertTrue(heldout.names_compatible(td_name, full), (td_name, full))

    def test_different_people_are_not_compatible(self):
        for td_name, full in (("Zverev A.", "Alexander Bublik"), ("Zhang Z.", "Shuai Zhang"),
                              ("Ruse G.", "Gabriela Lee"), ("Sakkari M.", "Tatjana Maria"),
                              ("Tam Sin Hang", "Sin Tam"), ("Amariei I. D.", "Ilinca Amariei")):
            self.assertFalse(heldout.names_compatible(td_name, full), (td_name, full))


class DuplicateTests(unittest.TestCase):
    def test_version_1_counted_the_spelling_variants_twice(self):
        matches, _, _ = assemble(*umag(), version=1)
        self.assertEqual(Counter(m["source"] for m in matches), {"tml": 4, "tennisdata": 2})

    def test_a_match_in_both_providers_appears_once_from_tml(self):
        matches, _, report = assemble(*umag())
        self.assertEqual(len(matches), 4)
        self.assertTrue(all(m["source"] == "tml" for m in matches))
        self.assertEqual(report["TennisData.app rows matched to TML rows by compatible names, round and edition"], 2)
        self.assertTrue(all(m["stats"]["w"]["svpt"] == 60 for m in matches))  # TML's record, with its statistics

    def test_one_person_gets_one_identity_across_providers(self):
        matches, _, report = assemble(*umag())
        merida = [m for m in matches if "Merida" in m["winner_name"]]
        self.assertEqual({m["winner_id"] for m in merida}, {210017})
        kinds = {p["kind"] for p in report["review"]["players"]}
        self.assertIn("resolved through TennisData.app crosswalk", kinds)

    def test_names_without_initials_and_a_blank_team_event_round(self):
        tml_rows = [tml(20260916, "Sin Hang Tam", "T0LD", "Boris Arias", "A0BB", tourney_id="M-DC-2026-WG2-R1-BOL-HKG",
                        number="3", round_name="RR", name="Davis Cup WG2 R1: BOL vs HKG")]
        td_rows = [td_row(9, "2026-09-16", "Tam Sin Hang", "562655", "Arias B.", "106262",
                          tournament="Davis Cup - World Group II ATP", round_name="")]
        matches, _, _ = assemble(tml_rows, td_rows, {("ATP", "A0BB"): 106262}, {("ATP", "106262"): 106262})
        self.assertEqual([m["source"] for m in matches], ["tml"])
        version_1, _, _ = assemble(tml_rows, td_rows, {("ATP", "A0BB"): 106262}, {("ATP", "106262"): 106262},
                                   version=1)
        self.assertEqual(len(version_1), 2)


class VallejoTests(unittest.TestCase):
    """TennisData.app's crosswalk sends 'Vallejo D.' (424916) to Sackmann 118808, a different Daniel Vallejo (MEX,
    born 1984), because Sackmann files Paraguay's Davis Cup matches under that id. TML's ATP code V0DP is Adolfo
    Daniel Vallejo (209226)."""

    def setUp(self):
        self.tml_rows = [tml(20260713, "Adolfo Daniel Vallejo", "V0DP", "Miguel Damas", "D0CN", tourney_id="2026-316",
                             name="Bastad")]
        self.td_rows = [
            td_row(1, "2026-07-13", "Damas M.", "557609", "Vallejo D.", "424916", tournament="Bastad ATP", winner="2"),
            # A match TML does not have: kept as a genuine addition.
            td_row(2, "2026-09-02", "Vallejo D.", "424916", "Feldbausch K.", "151477", tournament="Tokyo ATP"),
        ]
        self.tml_links = {("ATP", "V0DP"): 209226}
        self.td_links = {("ATP", "424916"): 118808}

    def test_the_tml_identity_is_used_and_the_wrong_crosswalk_entry_is_flagged(self):
        matches, _, report = assemble(self.tml_rows, self.td_rows, self.tml_links, self.td_links)
        self.assertEqual(len(matches), 2)
        tokyo = next(m for m in matches if m["source"] == "tennisdata")
        self.assertEqual(tokyo["winner_id"], 209226)
        conflict = [p for p in report["review"]["players"] if p["kind"].startswith("conflict: TennisData.app crosswalk")]
        self.assertEqual([(p["td_id"], p["crosswalk_sackmann_id"], p["used_id"]) for p in conflict],
                         [("424916", 118808, 209226)])

    def test_version_1_used_the_wrong_player(self):
        matches, _, _ = assemble(self.tml_rows, self.td_rows, self.tml_links, self.td_links, version=1)
        self.assertIn(118808, {m["winner_id"] for m in matches if m["source"] == "tennisdata"})


class RepeatMeetingTests(unittest.TestCase):
    def test_meetings_in_consecutive_editions_stay_separate(self):
        """The same pair, same round, a week apart. Montreal is in both providers; Cincinnati's second meeting is
        in TennisData.app only, so it is a genuine addition and must not be merged into Montreal's."""
        tml_rows = [
            tml(20260804, "Jannik Sinner", "S0AG", "Alexander Zverev", "Z355", tourney_id="2026-421", name="Montreal"),
            tml(20260804, "Daniel Merida", "M0N7", "Taylor Fritz", "F0AB", tourney_id="2026-421", number="2",
                name="Montreal"),
            tml(20260804, "Carlos Alcaraz", "A0E2", "Jack Draper", "D0FJ", tourney_id="2026-421", number="3",
                name="Montreal"),
        ]
        td_rows = [
            td_row(5, "2026-08-04", "Alcaraz C.", "1", "Draper J.", "2", tournament="Montreal ATP"),
            td_row(1, "2026-08-04", "Sinner J.", "206173", "Zverev A.", "100644", tournament="Montreal ATP"),
            td_row(2, "2026-08-04", "Merida Aguilar D.", "122001", "Fritz T.", "126203", tournament="Montreal ATP"),
            td_row(3, "2026-08-11", "Sinner J.", "206173", "Zverev A.", "100644", tournament="Cincinnati ATP"),
            td_row(4, "2026-08-11", "Fritz T.", "126203", "Merida Aguilar D.", "122001", tournament="Cincinnati ATP"),
        ]
        tml_links = {("ATP", "S0AG"): 206173, ("ATP", "Z355"): 100644, ("ATP", "F0AB"): 126203}
        td_links = {("ATP", "206173"): 206173, ("ATP", "100644"): 100644, ("ATP", "126203"): 126203,
                    ("ATP", "122001"): 210017}
        matches, _, _ = assemble(tml_rows, td_rows, tml_links, td_links)
        self.assertEqual(Counter(m["source"] for m in matches), {"tml": 3, "tennisdata": 2})
        cincinnati = [m for m in matches if m["source"] == "tennisdata"]
        self.assertEqual({m["tourney_date"] for m in cincinnati}, {20260811})
        self.assertIn(210017, {m["loser_id"] for m in cincinnati})

    def test_round_robin_and_final_of_one_edition_stay_separate(self):
        """A blank-round TennisData.app round-robin row fits both TML rows of the pair; the final is claimed by the
        TennisData.app final, so the round-robin row links to the round robin."""
        tml_rows = [tml(20261101, "Taylor Fritz", "F0AB", "Daniel Merida", "M0N7", tourney_id="2026-605",
                        number="1", round_name="RR", name="Finals"),
                    tml(20261104, "Daniel Merida", "M0N7", "Taylor Fritz", "F0AB", tourney_id="2026-605",
                        number="15", round_name="F", name="Finals")]
        td_rows = [td_row(1, "2026-11-01", "Fritz T.", "126203", "Merida Aguilar D.", "122001",
                          tournament="Finals - Turin ATP", round_name=""),
                   td_row(2, "2026-11-04", "Merida Aguilar D.", "122001", "Fritz T.", "126203",
                          tournament="Finals - Turin ATP", round_name="F")]
        matches, _, report = assemble(tml_rows, td_rows, {("ATP", "F0AB"): 126203},
                                      {("ATP", "126203"): 126203, ("ATP", "122001"): 210017})
        self.assertEqual(sorted(m["round"] for m in matches), ["F", "RR"])
        self.assertTrue(all(m["source"] == "tml" for m in matches))
        self.assertEqual(report["review"]["possible duplicates left out"], [])


class AmbiguityTests(unittest.TestCase):
    def test_a_row_that_fits_two_matches_is_left_out_and_listed_not_merged(self):
        tml_rows = [tml(20260713, "Zhizhen Zhang", "Z0A", "Xiaofei Wang", "W0A", number="1"),
                    tml(20260713, "Ze Zhang", "Z0B", "Xinyu Wang", "W0B", number="2")]
        td_rows = [td_row(1, "2026-07-13", "Zhang Z.", "11", "Wang X.", "22")]
        matches, _, report = assemble(tml_rows, td_rows, {}, {}, people={})
        self.assertEqual([m["source"] for m in matches], ["tml", "tml"])
        listed = report["review"]["possible duplicates left out"]
        self.assertEqual([(item["td_match_id"], item["reason"]) for item in listed], [("1", "several TML rows fit")])
        version_1, _, _ = assemble(tml_rows, td_rows, {}, {}, version=1, people={})
        self.assertEqual(len(version_1), 3)


class IdentityTests(unittest.TestCase):
    def test_an_unverified_player_gets_a_provider_only_id_not_a_namesake(self):
        """Version 1 guessed Sackmann 118808 for any unlinked 'Vallejo D.' by a unique surname and initial."""
        td_rows = [td_row(1, "2026-09-02", "Vallejo D.", "777", "Feldbausch K.", "151477", tournament="Tokyo ATP")]
        matches, _, report = assemble([], td_rows, {}, {})
        self.assertEqual(matches[0]["winner_id"], provider_only_id("tennisdata", "ATP", "777"))
        self.assertIn("unresolved TennisData.app player (provider-only id)", {p["kind"] for p in report["review"]["players"]})
        version_1, _, _ = assemble([], td_rows, {}, {}, version=1)
        self.assertEqual(version_1[0]["winner_id"], 118808)

    def test_two_tml_ids_for_one_person_resolve_together(self):
        """TML gives some WTA players two ids (Kaitlin Quevedo: 259733 and 269267)."""
        people = {259733: ("Kaitlin", "Quevedo"), 215000: ("Ana", "Bogdan"), 216000: ("Ena", "Shibahara")}
        tml_rows = [tml(20260713, "Kaitlin Quevedo", "259733", "Ana Bogdan", "215000", tourney_id="2026-2063",
                        name="Iasi", tour="WTA"),
                    tml(20260803, "Ena Shibahara", "216000", "Kaitlin Quevedo", "269267", tourney_id="2026-806",
                        name="Toronto", tour="WTA")]
        td_rows = [td_row(1, "2026-07-13", "Quevedo K.", "937862", "Bogdan A.", "5", tournament="Iasi WTA", tour_type="2"),
                   td_row(2, "2026-08-03", "Shibahara E.", "6", "Quevedo K.", "937862", tournament="Toronto WTA",
                          tour_type="2"),
                   td_row(3, "2026-09-21", "Quevedo K.", "937862", "Lys E.", "7", tournament="Seoul WTA", tour_type="2")]
        names = {("WTA", i): {"first": f, "last": l, "keys": sackmann_name_keys(f, l)} for i, (f, l) in people.items()}
        history = [dict(sackmann_match(i, 999999, "R32", n, date=20250106, tourney=f"H{n}"), tour="WTA")
                   for n, i in enumerate(people)]
        tml_links = {("WTA", "215000"): 215000, ("WTA", "216000"): 216000}
        matches, _, report = heldout.assemble(tml_rows, td_rows, history, names, tml_links, {}, [], START, END,
                                              SNAPSHOT)
        quevedo = {m["winner_id"] if "Quevedo" in m["winner_name"] else m["loser_id"] for m in matches}
        self.assertEqual(quevedo, {259733})  # one person: both TML ids and the TennisData.app id
        self.assertEqual(len(matches), 3)

    def test_linked_ids_whose_names_disagree_are_not_merged(self):
        pairs = [(td_row(1, "2026-07-13", "Amariei I. D.", "505128", "Bogdan A.", "5", tour_type="2"),
                  tml(20260713, "Ilinca Amariei", "221168", "Ana Bogdan", "215000", tour="WTA"), True)]
        people = heldout.player_links(pairs, {})
        self.assertNotIn(("WTA", "505128"), people["links"])
        self.assertEqual([c["td_ids"] for c in people["conflicts"]], [["505128"]])


class GuardTests(unittest.TestCase):
    def test_a_duplicate_with_different_ids_is_detected(self):
        tml_copy = tml_match(tml(20260608, "Elena Gabriela Ruse", "211817", "Elise Mertens", "210722",
                                 name="Hertogenbosch", tour="WTA"), {}, 20260608)
        tml_copy["match_day"] = 20260611
        td_copy = dict(tml_copy, source="tennisdata", key=("WTA", "TD-x", "1", "R32"), winner_name="Ruse G.",
                       loser_name="Mertens E.", winner_id=-5, loser_id=210722, match_day=20260611)
        found = heldout.cross_source_duplicates([tml_copy, td_copy], {}, {td_copy["key"]: ("WTA", "x", 20260608)})
        self.assertEqual(found, [(td_copy["key"], tml_copy["key"])])

    def test_the_build_stops_if_a_duplicate_slips_through(self):
        with mock.patch.object(heldout, "link_remaining", return_value=([], [])):
            with self.assertRaises(ValueError):
                assemble(*umag())


class ChronologyTests(unittest.TestCase):
    """Elo, form, inactivity, serve-return profiles and round-aware values from the corrected stream equal those
    from a stream built by hand with every real match once; and nothing later changes an earlier row."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        from matchup_dna.profiles import STATS
        settings = {"settings": {t: {"half_life": 52, "prior_matches": 4, "representation": "adjusted"}
                                 for t in ("ATP", "WTA")},
                    "means": {t: {s: [0.5, 60.0] for s in STATS} for t in ("ATP", "WTA")}}
        self.settings = Path(self.directory.name) / "profile_settings.json"
        self.settings.write_text(json.dumps(settings), encoding="utf-8")
        _, self.history = sackmann_people()

    def tearDown(self):
        self.directory.cleanup()

    def rows(self, stream):
        from matchup_dna.features import build_rows
        from matchup_dna.phase4_features import augment
        matches = self.history + stream
        return augment(build_rows(matches, start=20250101), matches, self.settings, start=20250101)

    def clean_stream(self):
        """Every real match once, from TML, with the identities a person would assign."""
        tml_rows, _, tml_links, _ = umag()
        links = {**tml_links, ("ATP", "M0N7"): 210017}
        dates = {"2026-439": 20260713, "2026-319": 20260721}
        return [tml_match(row, links, dates[row["tourney_id"]]) for row in tml_rows]

    def test_the_corrected_stream_equals_one_built_by_hand(self):
        corrected, _, _ = assemble(*umag())
        self.assertEqual(self.rows(corrected), self.rows(self.clean_stream()))

    def test_each_match_updates_ratings_once(self):
        from matchup_dna.elo import ELO_K, run_elo
        for version, extra in ((2, 0), (1, 1)):
            stream, _, _ = assemble(*umag(), version=version)
            predictions, _ = run_elo(self.history + stream, ELO_K)
            sesko = sum(212949 in (p["match"]["winner_id"], p["match"]["loser_id"]) for p in predictions)
            self.assertEqual(sesko, 1 + 2 + extra)  # history 1; Umag R32 and Kitzbuhel; version 1 also the copy

    def test_later_matches_never_change_earlier_rows(self):
        stream, _, _ = assemble(*umag())
        changed = copy.deepcopy(stream)
        last = max(changed, key=lambda m: m["tourney_date"])
        last["winner_id"], last["loser_id"] = last["loser_id"], last["winner_id"]
        before = [r for r in self.rows(stream) if r["tourney_date"] < last["tourney_date"]]
        after = [r for r in self.rows(changed) if r["tourney_date"] < last["tourney_date"]]
        self.assertTrue(before)
        self.assertEqual(before, after)


class ReconciliationTests(unittest.TestCase):
    """The independent checks in phase4_correction catch the footprints of duplicates and identity errors."""

    def test_the_original_duplicates_leave_a_schedule_clash_and_the_corrected_stream_none(self):
        from matchup_dna.phase4_correction import repeated_rounds, schedule_clashes
        original, _, _ = assemble(*umag(), version=1)
        corrected, _, _ = assemble(*umag())
        self.assertTrue(schedule_clashes(original))      # Sesko in "Umag" and in the TennisData.app copy of it
        self.assertEqual(schedule_clashes(corrected), [])
        self.assertEqual(repeated_rounds(corrected), [])

    def test_consecutive_weeks_are_not_a_clash(self):
        from matchup_dna.phase4_correction import schedule_clashes
        week_1 = sackmann_match(1, 2, "R32", 1, date=20260803, tourney="Montreal")
        week_2 = sackmann_match(1, 3, "R32", 1, date=20260810, tourney="Cincinnati")
        self.assertEqual(schedule_clashes([week_1, week_2]), [])

    def test_names_flag_wrong_merges_and_splits(self):
        from matchup_dna.phase4_correction import identity_names
        merged = [dict(sackmann_match(1, 2, "R32", 1), winner_name="Daniel Vallejo", loser_name="Ziga Sesko"),
                  dict(sackmann_match(1, 2, "R16", 2), winner_name="Daniel Merida", loser_name="Sesko Z.")]
        mixed, _ = identity_names(merged)
        self.assertEqual([m["player"] for m in mixed], [1])
        split = [dict(sackmann_match(5, 2, "R32", 1), winner_name="Xinran Sun", loser_name="Ziga Sesko"),
                 dict(sackmann_match(6, 2, "R32", 2, tourney="T2"), winner_name="Xinran Sun", loser_name="Ziga Sesko")]
        _, found = identity_names(split)
        self.assertEqual([s["ids"] for s in found], [[5, 6]])


def provider_files_present():
    try:
        from matchup_dna import tennisdata as td
        from matchup_dna import tennisismylife as tml
        return bool(td.provider_files()) and all(Path(p).exists() for p in tml.tml_files())
    except Exception:
        return False


# The 68 TennisData.app rows (65 rated) the original held-out build added a second time (erratum 1 diagnostics).
KNOWN_DUPLICATES = (
    ("ATP", "13949138"), ("ATP", "14661773"), ("ATP", "15167747"), ("ATP", "17826320"), ("ATP", "17923275"),
    ("ATP", "18091788"), ("ATP", "19337520"), ("ATP", "20671587"), ("ATP", "23823618"), ("ATP", "23954708"),
    ("ATP", "27043401"), ("ATP", "28906296"), ("ATP", "35315999"), ("ATP", "37318431"), ("ATP", "38312744"),
    ("ATP", "39468132"), ("ATP", "43775024"), ("ATP", "44441554"), ("ATP", "47374906"), ("ATP", "47670669"),
    ("ATP", "48436489"), ("ATP", "52330064"), ("ATP", "56169452"), ("ATP", "56732187"), ("ATP", "57730694"),
    ("ATP", "58471338"), ("ATP", "58868958"), ("ATP", "62545874"), ("ATP", "64177778"), ("ATP", "64826798"),
    ("ATP", "65224076"), ("ATP", "66564816"), ("ATP", "68801087"), ("ATP", "71537176"), ("ATP", "72063052"),
    ("ATP", "72355495"), ("ATP", "72721098"), ("ATP", "74941940"), ("ATP", "82021156"), ("ATP", "83329036"),
    ("ATP", "84723480"), ("ATP", "85634656"), ("ATP", "87384207"), ("ATP", "91274146"), ("ATP", "93377301"),
    ("ATP", "99842280"), ("ATP", "99859487"), ("WTA", "23404061"), ("WTA", "29293741"), ("WTA", "31464640"),
    ("WTA", "40444751"), ("WTA", "41619712"), ("WTA", "42696994"), ("WTA", "45671702"), ("WTA", "45881532"),
    ("WTA", "49089848"), ("WTA", "65493870"), ("WTA", "66123454"), ("WTA", "68205150"), ("WTA", "68597066"),
    ("WTA", "68618088"), ("WTA", "81917572"), ("WTA", "85532042"), ("WTA", "88454977"), ("WTA", "90300523"),
    ("WTA", "91544217"), ("WTA", "91982586"), ("WTA", "98465243"),
)


@unittest.skipUnless(provider_files_present(), "private provider files not present")
class RealHeldOutTests(unittest.TestCase):
    def test_every_known_duplicate_links_to_a_tml_row_using_sealed_rows_only(self):
        from matchup_dna import tennisdata as td
        from matchup_dna import tennisismylife as tml
        from matchup_dna.audit_tennisdata import sackmann_overlap
        from matchup_dna.crosswalk import load_player_names
        overlap, names = sackmann_overlap(), load_player_names()
        tml_links, td_links = heldout.crosswalks(overlap, names)
        excluded = heldout.excluded_tournaments(overlap, names)
        tml_rows = [r for r in tml.load_tml() if r["sealed"]]
        td_rows = [r for r in td.load_provider() if r["sealed"]]
        self.assertTrue(all("winner_id" not in r for r in tml_rows) and all("winner_code" not in r for r in td_rows))
        tml_window, td_window, _, td_editions = heldout.window_rows(tml_rows, td_rows, excluded, START, END, SNAPSHOT)
        pairs, _, review, _, _ = heldout.link_rows(td_window, tml_window, td_links, tml_links, td_editions)
        linked = {(row["tour"], row["match_id"]) for row, _, _ in pairs}
        self.assertEqual(len(KNOWN_DUPLICATES), 68)
        self.assertEqual(set(KNOWN_DUPLICATES) - linked, set())
        self.assertEqual(review, [])


if __name__ == "__main__":
    unittest.main()

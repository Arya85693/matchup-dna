import datetime
import unittest

from matchup_dna.crosswalk import (
    build_crosswalk, link_by_ids, link_matches, provider_name_key, sackmann_name_keys,
)

NAMES = {
    ("ATP", 10): ("Jannik", "Sinner"),
    ("ATP", 11): ("Martin", "Sinner"),
    ("ATP", 20): ("Alexander", "Zverev"),
    ("ATP", 21): ("Mischa", "Zverev"),
    ("ATP", 30): ("Bu", "Yunchaokete"),
    ("ATP", 40): ("Pablo", "Carreno Busta"),
}
NAMES = {key: {"first": first, "last": last, "keys": sackmann_name_keys(first, last)}
         for key, (first, last) in NAMES.items()}


def sackmann(winner, loser, date=20250106, tour="ATP"):
    return {"tour": tour, "tourney_date": date, "winner_id": winner, "loser_id": loser,
            "winner_name": "", "loser_name": ""}


def provider(home, away, day="2025-01-08", home_id="h", away_id="a", match_id="1", tour="ATP"):
    return {"tour": tour, "day": datetime.date.fromisoformat(day), "home_name": home, "away_name": away,
            "home_id": home_id, "away_id": away_id, "match_id": match_id}


class NameKeyTests(unittest.TestCase):
    def test_provider_names(self):
        self.assertEqual(provider_name_key("Carreno-Busta P."), ("carrenobusta", "p"))
        self.assertEqual(provider_name_key("Struff J-L."), ("struff", "j"))
        self.assertEqual(provider_name_key("Galan D. E."), ("galan", "d"))
        self.assertEqual(provider_name_key("O'Connell C."), ("oconnell", "c"))
        self.assertIsNone(provider_name_key("Sinner"))

    def test_sackmann_keys_include_a_tagged_reversed_order(self):
        keys = sackmann_name_keys("Bu", "Yunchaokete")
        self.assertEqual(keys["direct"], ("yunchaokete", "b"))
        self.assertEqual(keys["reversed"], ("bu", "y"))
        self.assertEqual(sackmann_name_keys("Pablo", "Carreño Busta")["direct"], ("carrenobusta", "p"))


class LinkTests(unittest.TestCase):
    def test_surname_alone_never_links(self):
        matches = [sackmann(11, 21)]
        result = link_matches([provider("Sinner J.", "Zverev A.")], matches, NAMES)[0]
        self.assertEqual(result["status"], "no candidate")

    def test_full_key_and_window_link_and_record_the_sides(self):
        matches = [sackmann(20, 10)]
        result = link_matches([provider("Sinner J.", "Zverev A.")], matches, NAMES)[0]
        self.assertEqual((result["status"], result["home"]), ("linked", "loser"))
        late = link_matches([provider("Sinner J.", "Zverev A.", day="2025-01-30")], matches, NAMES)[0]
        self.assertEqual(late["status"], "no candidate")

    def test_two_candidates_are_ambiguous_not_merged(self):
        matches = [sackmann(10, 20, 20250106), sackmann(20, 10, 20250113)]
        result = link_matches([provider("Sinner J.", "Zverev A.", day="2025-01-14")], matches, NAMES)[0]
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["match"])

    def test_a_sackmann_match_claimed_by_two_rows_links_neither(self):
        matches = [sackmann(10, 20)]
        rows = [provider("Sinner J.", "Zverev A.", match_id="1"), provider("Zverev A.", "Sinner J.", match_id="2")]
        self.assertEqual([r["status"] for r in link_matches(rows, matches, NAMES)], ["ambiguous", "ambiguous"])

    def test_reversed_names_are_tagged(self):
        result = link_matches([provider("Bu Y.", "Sinner J.")], [sackmann(30, 10)], NAMES)[0]
        self.assertEqual(result["status"], "linked")
        self.assertTrue(result["reversed"])
        direct = link_matches([provider("Carreno-Busta P.", "Sinner J.")], [sackmann(40, 10)], NAMES)[0]
        self.assertFalse(direct["reversed"])

    def test_tours_never_mix(self):
        result = link_matches([provider("Sinner J.", "Zverev A.", tour="WTA")], [sackmann(10, 20)], NAMES)[0]
        self.assertEqual(result["status"], "no candidate")


class CrosswalkTests(unittest.TestCase):
    def test_consistent_links_are_accepted(self):
        matches = [sackmann(10, 20, 20250106), sackmann(10, 40, 20250203)]
        rows = [provider("Sinner J.", "Zverev A.", "2025-01-08", "p10", "p20", "1"),
                provider("Carreno-Busta P.", "Sinner J.", "2025-02-05", "p40", "p10", "2")]
        crosswalk = build_crosswalk(link_matches(rows, matches, NAMES))
        self.assertEqual(crosswalk["links"], {("ATP", "p10"): 10, ("ATP", "p20"): 20, ("ATP", "p40"): 40})
        self.assertEqual(crosswalk["support"][("ATP", "p10")][10], 2)
        self.assertEqual(crosswalk["conflicts"], [])

    def test_one_provider_id_with_two_sackmann_ids_is_left_out(self):
        matches = [sackmann(10, 20, 20250106), sackmann(11, 40, 20250203)]
        rows = [provider("Sinner J.", "Zverev A.", "2025-01-08", "p10", "p20", "1"),
                provider("Sinner M.", "Carreno-Busta P.", "2025-02-05", "p10", "p40", "2")]
        crosswalk = build_crosswalk(link_matches(rows, matches, NAMES))
        self.assertNotIn(("ATP", "p10"), crosswalk["links"])
        self.assertEqual(crosswalk["conflicts"][0]["sackmann_ids"], {10: 1, 11: 1})

    def test_two_provider_ids_with_one_sackmann_id_are_both_left_out(self):
        matches = [sackmann(10, 20, 20250106), sackmann(10, 40, 20250203)]
        rows = [provider("Sinner J.", "Zverev A.", "2025-01-08", "p10", "p20", "1"),
                provider("Sinner J.", "Carreno-Busta P.", "2025-02-05", "x10", "p40", "2")]
        crosswalk = build_crosswalk(link_matches(rows, matches, NAMES))
        self.assertNotIn(("ATP", "p10"), crosswalk["links"])
        self.assertNotIn(("ATP", "x10"), crosswalk["links"])
        self.assertIn(("ATP", "p20"), crosswalk["links"])

    def test_second_pass_uses_validated_ids_only(self):
        matches = [sackmann(10, 20, 20250106), sackmann(10, 20, 20250303)]
        links = {("ATP", "p10"): 10, ("ATP", "p20"): 20}
        rows = [provider("Siner J.", "Zverev A.", "2025-03-05", "p10", "p20", "9"),
                provider("Siner J.", "Nobody N.", "2025-03-05", "p10", "p99", "8")]
        found = link_by_ids(rows, matches, links)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["match"]["tourney_date"], 20250303)
        self.assertEqual(found[0]["home"], "winner")


if __name__ == "__main__":
    unittest.main()

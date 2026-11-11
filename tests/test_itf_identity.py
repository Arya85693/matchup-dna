"""ITF extension identities: name keys, the learned country codes, and every resolution status."""
import unittest

from matchup_dna import itf_identity as i

PLAYERS = {("ATP", 1): {"name": "Yassine Dlimi", "ioc": "MAR", "dob": 19980101},
           ("ATP", 2): {"name": "Pedro Rodrigues", "ioc": "POR", "dob": 20060101},
           ("ATP", 3): {"name": "Pedro Rodrigues", "ioc": "BRA", "dob": 19990101},
           ("ATP", 4): {"name": "Ali Yazdani", "ioc": "IRI", "dob": 20000101},
           ("ATP", 5): {"name": "Old Timer", "ioc": "USA", "dob": 19500101},
           ("WTA", 1): {"name": "Sapfo Sakellaridi", "ioc": "GRE", "dob": 20000101}}


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.ids = i.Identities(PLAYERS, active={("ATP", 1), ("ATP", 2), ("ATP", 3), ("ATP", 4), ("WTA", 1)})

    def test_name_keys_ignore_order_accents_and_slug_numbers(self):
        self.assertEqual(i.name_key("dlimi-yassine"), i.name_key("Yassine Dlimi"))
        self.assertEqual(i.name_key("rodrigues-pedro-2006"), i.name_key("Pedro Rodrigues"))
        self.assertEqual(i.name_key("Çağla Büyükakçay"), i.name_key("cagla-buyukakcay"))

    def test_unique_names_verify_and_teach_countries(self):
        people = [("ATP", "dlimi-yassine", "Morocco")] * 3 + [("ATP", "yazdani-ali", "Iran")] * 3
        self.assertEqual(self.ids.learn_countries(people), {"Morocco": "MAR", "Iran": "IRI"})
        self.assertEqual(self.ids.resolve("ATP", "flashscore", "x1", "dlimi-yassine", "Morocco"), ("verified", 1))

    def test_namesakes_need_the_country(self):
        self.ids.countries = {"Portugal": "POR", "Spain": "ESP"}
        self.assertEqual(self.ids.resolve("ATP", "flashscore", "p1", "rodrigues-pedro-2006", "Portugal"),
                         ("verified_country", 2))
        self.assertEqual(self.ids.resolve("ATP", "flashscore", "p2", "rodrigues-pedro", "Spain"), ("ambiguous", None))

    def test_a_country_disagreement_is_a_conflict(self):
        self.ids.countries = {"Morocco": "MAR", "France": "FRA"}
        self.assertEqual(self.ids.resolve("ATP", "flashscore", "x9", "dlimi-yassine", "France"), ("conflict", None))

    def test_neutral_athletes_carry_no_country(self):
        people = [("ATP", "yazdani-ali", "World")] * 5
        self.assertEqual(self.ids.learn_countries(people), {})
        self.ids.countries = {"World": "RUS"}                    # even a mapping learned elsewhere is not used
        self.assertEqual(self.ids.resolve("ATP", "flashscore", "n1", "yazdani-ali", "World"), ("verified", 4))

    def test_new_players_get_a_stable_negative_id(self):
        status, pid = self.ids.resolve("ATP", "flashscore", "zeU8VKrH", "newcomer-nick", "Spain")
        self.assertEqual(status, "new_player")
        self.assertLess(pid, 0)
        self.assertEqual(pid, i.provider_id("flashscore", "zeU8VKrH"))

    def test_long_retired_namesakes_are_not_candidates_and_tours_are_separate(self):
        self.assertEqual(self.ids.candidates("ATP", "Old Timer"), [])
        self.assertEqual(self.ids.candidates("WTA", "sakellaridi-sapfo"), [1])
        self.assertEqual(self.ids.candidates("ATP", "sakellaridi-sapfo"), [])


if __name__ == "__main__":
    unittest.main()

"""Phase 5: linking Valuebetennis odds rows to the model's matches (matchup_dna.market_link)."""
import datetime
import unittest

from matchup_dna import market_link as ml


def vb_row(vb_id, day, first, second, ids, edition="E1", round_code=4, winner=0, midnight=False, tour="ATP",
           level="A", category="Main tour"):
    start = datetime.datetime.fromisoformat(day).replace(hour=0 if midnight else 12, tzinfo=datetime.timezone.utc)
    return {"vb_id": vb_id, "start": start, "day": start.date(), "midnight": midnight, "tournament": "Test Open",
            "edition": edition, "category": category, "level": level, "tour": tour, "surface": "Hard",
            "indoor": False, "round_code": round_code, "names": (first, second), "ids": ids, "open": (1.8, 2.0),
            "close": (None, None), "winner": winner, "score": "6-4 6-4", "duration": None, "source": "test"}


def model(match_id, date, a, b, a_id, b_id, round_name="R32", a_won=1, tour="ATP"):
    return {"match_id": f"{tour}|{match_id}|1|{round_name}", "period": "2021-2023 validation", "tour": tour,
            "tourney_date": date, "a_won": a_won, "a_id": a_id, "b_id": b_id, "a_name": a, "b_name": b,
            "round": round_name, "tourney_level": "A"}


class NameTests(unittest.TestCase):
    def test_name_keys_ignore_accents_case_hyphens_and_order(self):
        self.assertEqual(ml.name_key("Pablo Carreño-Busta"), ml.name_key("carreno busta pablo"))
        self.assertNotEqual(ml.name_key("Jannik Sinner"), ml.name_key("Martin Sinner"))

    def test_a_shared_surname_is_needed_for_a_variant(self):
        self.assertTrue(ml.shares_surname("Cori Gauff", "Coco Gauff"))
        self.assertTrue(ml.shares_surname("Jaume Antoni Munar Clar", "Jaume Munar"))
        self.assertFalse(ml.shares_surname("Taylor Fritz", "Taylor Townsend"))


class LinkTests(unittest.TestCase):
    def test_full_names_and_the_window_link_in_either_order(self):
        models = [model("2025-1", 20250106, "Jannik Sinner", "Luca Nardi", 1, 2)]
        rows = [vb_row(10, "2025-01-08", "Luca Nardi", "Jannik Sinner", ("v2", "v1"), winner=1)]
        result = ml.link(rows, models)
        self.assertEqual([(r["vb_id"], m["match_id"], same) for r, m, same in result["links"]],
                         [(10, "ATP|2025-1|1|R32", False)])
        self.assertEqual(result["crosswalk"], {("ATP", "v1"): frozenset({1}), ("ATP", "v2"): frozenset({2})})

    def test_a_surname_alone_never_links(self):
        models = [model("2025-1", 20250106, "Jannik Sinner", "Luca Nardi", 1, 2)]
        rows = [vb_row(10, "2025-01-08", "Martin Sinner", "Luca Nardi", ("v9", "v2"))]
        self.assertEqual(ml.link(rows, models)["links"], [])

    def test_outside_the_window_or_in_a_different_round_does_not_link(self):
        models = [model("2025-1", 20250106, "Jannik Sinner", "Luca Nardi", 1, 2)]
        late = vb_row(10, "2025-02-01", "Jannik Sinner", "Luca Nardi", ("v1", "v2"))
        final = vb_row(11, "2025-01-12", "Jannik Sinner", "Luca Nardi", ("v1", "v2"), round_code=12)
        self.assertEqual(ml.link([late, final], models)["links"], [])

    def test_a_row_that_fits_two_matches_is_listed_not_linked(self):
        models = [model("2025-1", 20250106, "Jannik Sinner", "Luca Nardi", 1, 2),
                  model("2025-2", 20250113, "Jannik Sinner", "Luca Nardi", 1, 2)]
        result = ml.link([vb_row(10, "2025-01-14", "Jannik Sinner", "Luca Nardi", ("v1", "v2"), edition="X")], models)
        self.assertEqual(result["links"], [])
        self.assertEqual([x["reason"] for x in result["review"]], ["row fits several model matches"])

    def test_a_second_meeting_a_week_later_goes_to_its_own_edition(self):
        """Halle then Mallorca: both odds rows fall in Halle's window; each links to its own tournament, decided
        by the edition the other, unambiguous rows of that event link to."""
        models = [model("2025-H", 20250616, "Ugo Humbert", "Sam Querrey", 1, 2),
                  model("2025-H", 20250616, "Alex Bolt", "Ben Shelton", 3, 4),
                  model("2025-M", 20250623, "Ugo Humbert", "Sam Querrey", 1, 2),
                  model("2025-M", 20250623, "Carlos Taberner", "Dan Evans", 5, 6)]
        models[1]["match_id"] = "ATP|2025-H|2|R32"
        models[3]["match_id"] = "ATP|2025-M|2|R32"
        rows = [vb_row(10, "2025-06-17", "Ugo Humbert", "Sam Querrey", ("v1", "v2"), edition="halle"),
                vb_row(11, "2025-06-17", "Alex Bolt", "Ben Shelton", ("v3", "v4"), edition="halle"),
                vb_row(12, "2025-06-24", "Ugo Humbert", "Sam Querrey", ("v1", "v2"), edition="mallorca"),
                vb_row(13, "2025-06-24", "Carlos Taberner", "Dan Evans", ("v5", "v6"), edition="mallorca")]
        pairs = {(r["vb_id"], m["match_id"]) for r, m, _ in ml.link(rows, models)["links"]}
        self.assertIn((10, "ATP|2025-H|1|R32"), pairs)
        self.assertIn((12, "ATP|2025-M|1|R32"), pairs)

    def test_one_real_match_keeps_one_row_and_placeholders_lose(self):
        models = [model("2025-1", 20250106, "Andrey Rublev", "Roberto Quiroz", 1, 2)]
        rows = [vb_row(10, "2025-01-08", "Andrey Rublev", "Roberto Quiroz", ("v1", "v2"), midnight=True, edition="A"),
                vb_row(11, "2025-01-08", "Andrey Rublev", "Roberto Quiroz", ("v1", "v2"), edition="B")]
        self.assertEqual([r["vb_id"] for r, _, _ in ml.link(rows, models)["links"]], [11])

    def test_a_name_variant_is_mapped_only_from_two_verified_opponent_matches(self):
        models = [model("2025-1", 20250106, "Coco Gauff", "Iga Swiatek", 1, 2, a_won=0),
                  model("2025-2", 20250113, "Coco Gauff", "Iga Swiatek", 1, 2, round_name="SF"),
                  model("2025-3", 20250120, "Iga Swiatek", "Elena Rybakina", 2, 3),
                  model("2025-4", 20250127, "Coco Gauff", "Elena Rybakina", 1, 3)]
        rows = [vb_row(10, "2025-01-20", "Iga Swiatek", "Elena Rybakina", ("w2", "w3"), edition="c"),
                vb_row(11, "2025-01-07", "Cori Gauff", "Iga Swiatek", ("w1", "w2"), winner=1, edition="a"),
                vb_row(12, "2025-01-17", "Cori Gauff", "Iga Swiatek", ("w1", "w2"), round_code=10, edition="b"),
                vb_row(13, "2025-01-28", "Cori Gauff", "Elena Rybakina", ("w1", "w3"), edition="d")]
        for row in rows:
            row["tour"] = "WTA"
        for m in models:
            m["tour"] = "WTA"
        result = ml.link(rows, models)
        self.assertEqual(result["variants"], {("WTA", "w1"): frozenset({1})})
        self.assertEqual(len(result["links"]), 4)

    def test_one_matching_surname_in_one_match_is_not_enough(self):
        models = [model("2025-1", 20250106, "Joaquin Aguilar Cardozo", "Luca Nardi", 1, 2),
                  model("2025-2", 20250113, "Luca Nardi", "Tomas Barrios", 2, 3)]
        rows = [vb_row(10, "2025-01-14", "Luca Nardi", "Tomas Barrios", ("v2", "v3"), edition="b"),
                vb_row(11, "2025-01-07", "Juan Carlos Manuel Aguilar", "Luca Nardi", ("v1", "v2"), edition="a")]
        result = ml.link(rows, models)
        self.assertEqual(result["variants"], {})
        self.assertNotIn(11, [r["vb_id"] for r, _, _ in result["links"]])

    def test_team_event_codes_are_not_compared_with_the_round(self):
        """Billie Jean King Cup Finals semifinal: code 16 says nothing about the round."""
        models = [model("2023-B", 20231107, "Marketa Vondrousova", "Leylah Fernandez", 1, 2, round_name="SF")]
        rows = [vb_row(10, "2023-11-10", "Marketa Vondrousova", "Leylah Fernandez", ("v1", "v2"), round_code=16,
                       level="D", category="Coupe Davis / BJK Cup")]
        self.assertEqual(len(ml.link(rows, models)["links"]), 1)

    def test_one_match_is_enough_when_a_name_only_adds_words(self):
        models = [model("2025-1", 20250106, "Aisam Ul Haq Qureshi", "Luca Nardi", 1, 2),
                  model("2025-2", 20250113, "Luca Nardi", "Tomas Barrios", 2, 3)]
        rows = [vb_row(10, "2025-01-14", "Luca Nardi", "Tomas Barrios", ("v2", "v3"), edition="b"),
                vb_row(11, "2025-01-07", "Aisam Qureshi", "Luca Nardi", ("v1", "v2"), edition="a")]
        result = ml.link(rows, models)
        self.assertEqual(result["variants"], {("ATP", "v1"): frozenset({1})})
        self.assertIn(11, [r["vb_id"] for r, _, _ in result["links"]])

    def test_a_player_the_model_holds_under_two_ids_with_one_name_maps_to_both(self):
        """Martin Landaluce has two Sackmann ids; one Valuebetennis id links to both."""
        models = [model("2025-1", 20250106, "Martin Landaluce", "Luca Nardi", 7, 2),
                  model("2025-2", 20250203, "Martin Landaluce", "Tomas Barrios", 8, 3)]
        rows = [vb_row(10, "2025-01-07", "Martin Landaluce", "Luca Nardi", ("v1", "v2"), edition="a"),
                vb_row(11, "2025-02-04", "Martin Landaluce", "Tomas Barrios", ("v1", "v3"), edition="b")]
        result = ml.link(rows, models)
        self.assertEqual(result["crosswalk"][("ATP", "v1")], frozenset({7, 8}))
        self.assertEqual(result["conflicts"], [])

    def test_two_different_people_with_one_vb_id_are_never_merged(self):
        models = [model("2025-1", 20250106, "Martin Landaluce", "Luca Nardi", 7, 2),
                  model("2025-2", 20250203, "Martin Sinner", "Tomas Barrios", 8, 3)]
        rows = [vb_row(10, "2025-01-07", "Martin Landaluce", "Luca Nardi", ("v1", "v2"), edition="a"),
                vb_row(11, "2025-02-04", "Martin Sinner", "Tomas Barrios", ("v1", "v3"), edition="b")]
        result = ml.link(rows, models)
        self.assertNotIn(("ATP", "v1"), result["crosswalk"])
        self.assertEqual(len(result["conflicts"]), 1)

    def test_qualifying_rows_are_removed_and_different_winners_are_left_out(self):
        models = [model("2025-1", 20250106, "Jannik Sinner", "Luca Nardi", 1, 2, a_won=1)]
        qualifying = vb_row(10, "2025-01-05", "Jannik Sinner", "Luca Nardi", ("v1", "v2"), round_code=2, level="G")
        self.assertEqual(ml.link([qualifying], models)["links"], [])
        wrong = vb_row(11, "2025-01-08", "Jannik Sinner", "Luca Nardi", ("v1", "v2"), winner=1)
        result = ml.link([wrong], models)
        self.assertEqual(result["links"], [])
        self.assertEqual(len(result["winner_mismatches"]), 1)


if __name__ == "__main__":
    unittest.main()

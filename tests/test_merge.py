import unittest

from matchup_dna.merge import combine
from test_round_aware import eight_draw


def stats(svpt):
    return {"ace": 1, "df": 1, "svpt": svpt, "1stIn": 30, "1stWon": 20, "2ndWon": 10, "SvGms": 8, "bpSaved": 1,
            "bpFaced": 2}


class UnsealedRowTests(unittest.TestCase):
    """Amendment 1: a held-out row unlocked by the frozen protocol must convert; a sealed row must not."""

    def test_unlocked_held_out_rows_convert_and_sealed_rows_do_not(self):
        import json
        import tempfile
        from pathlib import Path
        from matchup_dna import tennisismylife as tml
        from matchup_dna.merge import tml_match
        from test_tennisismylife import SealTests

        helper = SealTests()
        helper.setUp()
        try:
            protocol = Path(helper.directory.name) / "phase4.json"
            protocol.write_text(json.dumps({"phase": 4, "frozen": "2026-11-05"}), encoding="utf-8")
            unlocked = tml.load_tml(helper.directory.name, unseal_with=protocol)[1]
            self.assertTrue(unlocked["sealed"])
            match = tml_match(unlocked, {}, 20260601)
            self.assertEqual(match["outcome"], "completed")
            self.assertIn("stats", match)
            sealed = tml.load_tml(helper.directory.name)[1]
            with self.assertRaises(PermissionError):
                tml_match(sealed, {}, 20260601)
        finally:
            helper.tearDown()


class BackfillTests(unittest.TestCase):
    def test_a_blank_line_is_replaced_whole_and_sackmann_values_are_kept(self):
        rows = eight_draw()
        rows[0]["stats"] = {"w": {k: None for k in stats(0)}, "l": stats(55)}
        tml = dict(rows[0], key=("ATP", "TML-T1", "1", "QF"), source="tml", minutes=99,
                   stats={"w": stats(60), "l": stats(70)})
        merged, report = combine(rows, [(tml, rows[0], True)])
        filled = merged[0]
        self.assertEqual(filled["stats"]["w"]["svpt"], 60)
        self.assertEqual(filled["stats"]["l"]["svpt"], 55)
        self.assertEqual(filled["minutes"], 90)
        self.assertEqual(filled["backfilled"], ["w statistics"])
        self.assertIsNone(rows[0]["stats"]["w"]["svpt"])

    def test_nothing_is_taken_when_winners_differ(self):
        rows = eight_draw({0: {"minutes": None}})
        tml = dict(rows[0], key=("ATP", "TML-T1", "1", "QF"), source="tml", minutes=80)
        merged, report = combine(rows, [(tml, rows[0], False)])
        self.assertIsNone(merged[0]["minutes"])
        self.assertEqual(report["linked, winners differ: not used"], 1)


if __name__ == "__main__":
    unittest.main()

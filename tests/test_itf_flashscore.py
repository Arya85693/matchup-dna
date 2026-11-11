"""ITF extension, Flashscore reader: page blocks, the record format, outcomes, the archive and the latest state."""
import io
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from matchup_dna import itf_flashscore as fs

HEADER = "SA÷2¬~ZA÷ITF MEN - SINGLES: M15 Test 3 (Spain), clay¬ZEE÷x¬"


def match(mid, round_="Final", ab="3", ac="3", winner="1", home_sets=((6, None), (7, 7)), away_sets=((3, None), (6, 5)),
          start=1794301200):
    parts = [f"AA÷{mid}", f"AD÷{start}", f"AB÷{ab}", f"AC÷{ac}", f"ER÷{round_}", "PX÷p1", "AE÷One A.", "WU÷one-anna",
             "FU÷Spain", "PY÷p2", "AF÷Two B.", "WV÷two-bea", "FV÷Italy"]
    if winner:
        parts.append(f"AS÷{winner}")
    for (h, htb), (a, atb), keys in zip(home_sets, away_sets, fs.SET_KEYS):
        parts += [f"{keys[0]}÷{h}", f"{keys[1]}÷{a}"]
        if htb is not None:
            parts += [f"{keys[2]}÷{htb}", f"{keys[3]}÷{atb}"]
    return "¬".join(parts) + "¬"


def page(*blocks):
    script = "".join(f"cjs.initialFeeds['{name}'] = {{\n data: `{data}`,\n}};\n" for name, data in blocks)
    return f"<html><script>{script}</script></html>"


class ParseTests(unittest.TestCase):
    def test_header(self):
        h = fs.parse_header("ITF WOMEN - SINGLES: W35 Heraklion 3 (Greece), clay")
        self.assertEqual((h["tour"], h["name"], h["country"], h["surface"], h["level"], h["tier"]),
                         ("WTA", "W35 Heraklion 3", "Greece", "Clay", "35", 2))
        self.assertEqual(fs.parse_header("ITF MEN - SINGLES: M25 Montreal (Canada), hard (indoor)")["surface"], "Hard")
        main = fs.parse_header("ATP - SINGLES: Stockholm (Sweden), hard (indoor)")       # history, never scored
        self.assertEqual((main["tour"], main["itf"], main["tier"]), ("ATP", False, None))
        self.assertEqual(fs.parse_header("CHALLENGER WOMEN - SINGLES: Austin (USA), hard")["tour"], "WTA")
        self.assertTrue(fs.parse_header("ITF WOMEN - SINGLES: W15 Nules (Spain), clay")["itf"])
        self.assertIsNone(fs.parse_header("ITF MEN - DOUBLES: M15 Nules (Spain), clay"))

    def test_a_finished_match(self):
        feeds = fs.extract_feeds(page(("results", HEADER + "~" + match("abc12345"))))
        header, matches, skipped = fs.parse_page(feeds, "2026-11-11T00:00:00Z")
        m = matches[0]
        self.assertEqual((m["tour"], m["round"], m["start"], m["status"], m["outcome"], m["winner"], m["score"]),
                         ("ATP", "F", "2026-11-10T09:00:00Z", "finished", "completed", "home", "6-3 7-6(5)"))
        self.assertEqual((m["home"]["slug"], m["away"]["country"], m["tier"]), ("one-anna", "Italy", 1))

    def test_outcomes(self):
        retired = fs.extract_feeds(page(("results", HEADER + "~" + match("r1", home_sets=((6, None), (3, None)),
                                                                          away_sets=((2, None), (0, None))))))
        walkover = fs.extract_feeds(page(("results", HEADER + "~" + match("w1", home_sets=(), away_sets=()))))
        scheduled = fs.extract_feeds(page(("fixtures", HEADER + "~" + match("s1", ab="1", ac="1", winner=None,
                                                                            home_sets=(), away_sets=()))))
        self.assertEqual(fs.parse_page(retired, "t")[1][0]["outcome"], "retired")        # "6-2 3-0" is unfinished
        self.assertEqual(fs.parse_page(walkover, "t")[1][0]["outcome"], "walkover")
        s = fs.parse_page(scheduled, "t")[1][0]
        self.assertEqual((s["status"], s["outcome"], s["winner"], s["score"]), ("scheduled", None, None, ""))

    def test_each_match_once_and_unscored_rounds_skipped(self):
        data = HEADER + "~" + match("a1") + "~" + match("q1", round_="Qualification")
        feeds = fs.extract_feeds(page(("summary-results", data), ("results", data)))
        _, matches, skipped = fs.parse_page(feeds, "t")
        self.assertEqual([m["provider_match_id"] for m in matches], ["a1"])
        self.assertEqual(skipped, {"Qualification": 2})

    def test_score_from_the_winners_side(self):
        sets = [(6, 7, 3, 7), (4, 6, None, None)]
        self.assertEqual(fs.score_text(sets, "away"), "7-6(3) 6-4")
        self.assertEqual(fs.score_text(sets, "home"), "6-7(3) 4-6")


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def opener(self, html):
        seen = []

        def open_(request, timeout=None):
            seen.append((request.full_url, request.get_header("User-agent")))
            return FakeResponse(html.encode("utf-8"))
        open_.seen = seen
        return open_

    def test_a_page_is_archived_with_its_hashes(self):
        opener = self.opener(page(("results", HEADER + "~" + match("abc12345"))))
        meta = fs.fetch_event("itf-men-singles", "m15-test-3", self.dir, opener, retrieved_at="2026-11-11T01:00:00Z")
        self.assertEqual(opener.seen[0], (fs.BASE + "/tennis/itf-men-singles/m15-test-3/results/", fs.USER_AGENT))
        self.assertEqual(len(meta["page_sha256"]), 64)
        self.assertEqual(meta["feeds"], ["results"])
        self.assertTrue((self.dir / meta["file"]).exists())
        self.assertEqual(fs.archived(self.dir)[0]["slug"], "m15-test-3")

    def test_load_keeps_the_latest_state_of_each_match(self):
        before = self.opener(page(("fixtures", HEADER + "~" + match("abc12345", ab="1", ac="1", winner=None,
                                                                    home_sets=(), away_sets=()))))
        after = self.opener(page(("results", HEADER + "~" + match("abc12345"))))
        fs.fetch_event("itf-men-singles", "m15-test-3", self.dir, before, retrieved_at="2026-11-10T01:00:00Z")
        fs.fetch_event("itf-men-singles", "m15-test-3", self.dir, after, retrieved_at="2026-11-11T01:00:00Z")
        matches = fs.load(self.dir)
        self.assertEqual(len(matches), 1)
        self.assertEqual((matches[0]["status"], matches[0]["retrieved_at"]), ("finished", "2026-11-11T01:00:00Z"))
        self.assertEqual(fs.load(self.dir, since=20261111), [])          # started on 10 November

    def test_fetch_all_skips_archived_pages_when_resuming(self):
        opener = self.opener(page(("results", HEADER + "~" + match("abc12345"))))
        fs.fetch_event("itf-men-singles", "m15-test-3", self.dir, opener)
        calls = []
        with unittest.mock.patch.object(fs, "fetch_event", lambda c, s, d: calls.append((c, s)) or {"http_status": 200}):
            fs.fetch_all([("itf-men-singles", "m15-test-3"), ("itf-men-singles", "m15-other")], self.dir,
                         skip_archived=True, pause=0)
        self.assertEqual(calls, [("itf-men-singles", "m15-other")])


if __name__ == "__main__":
    unittest.main()

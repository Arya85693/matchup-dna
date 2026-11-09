"""Phase 6 provider records: the four timestamps, status mapping, and refusal of records that cannot be right."""
import datetime
import unittest

from matchup_dna.forecasting import records as rec
from matchup_dna.forecasting.providers import td_record
from matchup_dna.forecasting.records import MatchRecord
from test_heldout import td_row

RETRIEVED = "2026-11-05T12:31:00Z"


def record(**changes):
    values = dict(provider="p", provider_match_id="1", tour="ATP", circuit="tour", tournament="T", round="R32",
                  home_id="a", home_name="A", away_id="b", away_name="B", status=rec.SCHEDULED, retrieved_at=RETRIEVED)
    values.update(changes)
    return MatchRecord(**values)


class RecordTests(unittest.TestCase):
    def test_times_must_be_utc_and_explicit(self):
        self.assertEqual(rec.iso("2026-11-08T21:30:00+01:00"), "2026-11-08T20:30:00Z")
        with self.assertRaises(ValueError):
            rec.utc("2026-11-08T21:30:00")  # no timezone: refused, never guessed
        with self.assertRaises(ValueError):
            record(retrieved_at="2026-11-05 12:31")

    def test_impossible_records_are_refused(self):
        with self.assertRaises(ValueError):
            record(status=rec.SCHEDULED, winner_side="home")
        with self.assertRaises(ValueError):
            record(status=rec.COMPLETED)  # finished without a winner
        with self.assertRaises(ValueError):
            record(away_id="a")
        with self.assertRaises(ValueError):
            record(tour="ITF")

    def test_the_content_hash_ignores_only_the_retrieval_time(self):
        self.assertEqual(record().content_sha256(), record(retrieved_at="2026-11-06T00:00:00Z").content_sha256())
        self.assertNotEqual(record().content_sha256(), record(home_rank=5).content_sha256())


class TennisDataMappingTests(unittest.TestCase):
    def test_statuses_and_results(self):
        finished = td_record(td_row(1, "2026-07-13", "Sinner J.", "1", "Zverev A.", "2"), RETRIEVED)
        self.assertEqual((finished.status, finished.winner_side, finished.score), (rec.COMPLETED, "home", "6-3 6-3"))
        self.assertEqual(finished.event_time, "2026-07-13T12:00:00Z")
        walkover = td_record(dict(td_row(2, "2026-07-13", "A B.", "1", "C D.", "2", winner="2"),
                                  status_extra="WALKOVER"), RETRIEVED)
        self.assertEqual((walkover.status, walkover.winner_side, walkover.score), (rec.WALKOVER, "away", "W/O"))
        cancelled = td_record(dict(td_row(3, "2026-07-13", "A B.", "1", "C D.", "2"), status_extra="CANCELED",
                                   winner_code=""), RETRIEVED)
        self.assertEqual((cancelled.status, cancelled.winner_side), (rec.CANCELLED, None))
        retired = td_record(dict(td_row(4, "2026-07-13", "A B.", "1", "C D.", "2"), status_extra="RETIRED"), RETRIEVED)
        self.assertEqual((retired.status, retired.score), (rec.RETIRED, "6-3 6-3 RET"))
        scheduled = td_record(dict(td_row(5, "2026-07-13", "A B.", "1", "C D.", "2"), status="SCHEDULED",
                                   status_extra="SCHEDULED", winner_code=""), RETRIEVED)
        self.assertEqual((scheduled.status, scheduled.winner_side, scheduled.score), (rec.SCHEDULED, None, None))


if __name__ == "__main__":
    unittest.main()

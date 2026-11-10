"""Phase 8 shadow check: forecasts issued since a moment, on the official store and on the shadow store.

    python scripts/cloud/compare_stores.py <official.sqlite> <shadow.sqlite> <since, e.g. 2026-11-10T03:31:00Z>

For matches both forecast, the inputs and the probability should be identical. A match forecast on one side only is
listed with its start time: the shadow runs every 30 minutes and the laptop twice a day, so the shadow is expected to
forecast more, never fewer, of the matches listed in time.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from web.publisher.readonly import open_readonly  # noqa: E402


def label(store, uid):
    row = store.db.execute("SELECT sr.payload_json FROM match_observations o JOIN source_records sr "
                           "ON sr.record_id = o.record_id WHERE o.match_uid = ? ORDER BY sr.retrieved_at DESC LIMIT 1",
                           (uid,)).fetchone()
    p = json.loads(row[0]) if row else {}
    return f"{p.get('home_name')} v {p.get('away_name')} (start {p.get('event_time')})"


def main(official_path, shadow_path, since):
    official, shadow = open_readonly(official_path), open_readonly(shadow_path)
    try:
        a = {(r["match_uid"], r["model_version"]): r for r in official.predictions() if r["issued_at"] >= since}
        b = {(r["match_uid"], r["model_version"]): r for r in shadow.predictions() if r["issued_at"] >= since}
        both = sorted(set(a) & set(b))
        same = [k for k in both if a[k]["input_sha256"] == b[k]["input_sha256"] and a[k]["p_a"] == b[k]["p_a"]]
        print(f"since {since}: official {len(a)}, shadow {len(b)}; both {len(both)}, identical {len(same)}")
        for k in both:
            if k not in same:
                print(f"  differs: {k[1]} {label(official, k[0])}: {a[k]['p_a']} v {b[k]['p_a']}")
        for k in sorted(set(a) - set(b)):
            print(f"  official only: {k[1]} {label(official, k[0])}")
        for k in sorted(set(b) - set(a)):
            print(f"  shadow only:   {k[1]} {label(shadow, k[0])}")
        return 0 if len(same) == len(both) and not set(a) - set(b) else 1
    finally:
        official.close()
        shadow.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))

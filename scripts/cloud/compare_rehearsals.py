"""Phase 8 dry run: are two replay stores (the same days replayed on two machines) identical, input for input?

    python scripts/cloud/compare_rehearsals.py <laptop replay.sqlite> <github replay.sqlite>

Matches forecasts by match and model. "Identical" means the same input_sha256 (every input number written the same,
which is what the live store's "unchanged" rule needs) and the same probability. Where they differ, it shows which
inputs differ and by how much. Exit code 0 only if every forecast is identical and neither side has extras.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def load(path):
    from web.publisher.readonly import open_readonly
    store = open_readonly(path)
    try:
        return {(r["match_uid"], r["model_version"]): r for r in store.predictions()}
    finally:
        store.close()


def numbers(value, prefix=""):
    """Flattens nested inputs to {path: number}."""
    if isinstance(value, dict):
        return {k: v for key, item in value.items() for k, v in numbers(item, f"{prefix}{key}.").items()}
    if isinstance(value, list):
        return {k: v for i, item in enumerate(value) for k, v in numbers(item, f"{prefix}{i}.").items()}
    return {prefix[:-1]: value} if isinstance(value, (int, float)) and not isinstance(value, bool) else {}


def main(a_path, b_path):
    a, b = load(a_path), load(b_path)
    shared = sorted(set(a) & set(b))
    identical = [k for k in shared if a[k]["input_sha256"] == b[k]["input_sha256"] and a[k]["p_a"] == b[k]["p_a"]]
    print(f"forecasts: {len(a)} on the first machine, {len(b)} on the second, {len(shared)} in common")
    print(f"identical (inputs and probability): {len(identical)} of {len(shared)}")
    only = sorted(set(a) ^ set(b))
    if only:
        print(f"on one side only: {len(only)} (e.g. {only[:3]})")
    worst = 0.0
    for key in shared:
        if key in identical:
            continue
        x, y = a[key], b[key]
        dp = abs(x["p_a"] - y["p_a"])
        worst = max(worst, dp)
        ix = numbers(json.loads(x["content_json"])["inputs"])
        iy = numbers(json.loads(y["content_json"])["inputs"])
        diffs = sorted(((k, abs(ix[k] - iy[k])) for k in ix.keys() & iy.keys() if ix[k] != iy[k]), key=lambda kv: -kv[1])
        print(f"  {key[0]} {key[1]}: probability differs by {dp:.3g}; {len(diffs)} input(s) differ, largest "
              + ", ".join(f"{k} {d:.3g}" for k, d in diffs[:3]))
    if shared and len(identical) < len(shared):
        print(f"largest probability difference: {worst:.3g}")
    return 0 if shared and len(identical) == len(shared) and not only else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))

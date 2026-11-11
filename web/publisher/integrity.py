"""The integrity check that the cloud preflight and the website's status page both apply, so they cannot disagree.

`verify_store` recomputes every hash and every stored probability exactly. A probability that recomputes within
ROUNDING of its stored value is processor rounding, not a changed forecast: on 10 November 2026 a GitHub machine
recomputed a laptop forecast as 0.6499868570461047 against the stored 0.6499868570461048, a difference in the 16th
decimal place. Such a difference is a note. Everything else (the hash chain, the content hashes, any larger
difference) is a problem, checked exactly.
"""
import re

ROUNDING = 1e-12          # the largest recomputation difference that is processor rounding, not a changed forecast
RECOMPUTED = re.compile(r"^(?P<id>\w+): recomputed (?P<now>[-+0-9.eE]+), stored (?P<then>[-+0-9.eE]+)$")


def classify(found):
    """([problems], [notes]) from verify_store's findings."""
    problems, notes = [], []
    for problem in found:
        m = RECOMPUTED.match(problem)
        if m and abs(float(m["now"]) - float(m["then"])) <= ROUNDING:
            notes.append(f"{m['id'][:12]} recomputes {float(m['now']) - float(m['then']):+.1e} from its stored value "
                         "(processor rounding)")
        else:
            problems.append(problem)
    return problems, notes


def check(store):
    """([problems], [notes]) for a store: verify_store's findings, classified."""
    from matchup_dna.forecasting.api import verify_store
    return classify(verify_store(store))

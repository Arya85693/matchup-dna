"""Odds arithmetic for Phase 5: implied probabilities, the bookmaker margin, margin-free probabilities, and
expected value.

A decimal price o returns o per unit staked (stake included) if the bet wins, so its raw implied probability is
1 / o. In a two-player market the two raw probabilities add up to more than 1; the excess is the margin, and
their sum is the overround. Treating 1 / o as the fair probability would invent an "edge" that is only the
bookmaker's cut, so the margin has to be removed, and removing it needs an assumption about how the bookmaker
spread it between the two players. Four standard assumptions are implemented; each returns two probabilities
that sum to 1 (within floating-point error):

- multiplicative: scale both raw probabilities down in proportion (1/o_i divided by the overround);
- additive: take the same amount off each (1/o_i - margin / 2);
- power: raise both to one power k chosen so they sum to 1 (puts more of the margin on the longshot);
- shin: Shin's (1993) model of a market with a share z of insiders, solved for z.

Nothing here looks at outcomes. Which method fits best is a development-period question (phase5_experiment).
"""
import math

METHODS = ("multiplicative", "additive", "power", "shin")


def implied(odds):
    """Raw implied probabilities 1 / o for a pair of decimal prices."""
    return tuple(1.0 / o for o in odds)


def overround(odds):
    """Sum of the raw implied probabilities; 1.05 means a 5% margin."""
    return sum(implied(odds))


def _check(odds):
    if len(odds) != 2 or any(o is None or not o > 1.0 for o in odds):
        raise ValueError(f"need two decimal prices above 1.0, got {odds!r}")


def _bisect(function, low, high, tolerance=1e-13, iterations=200):
    """A root of a function that changes sign once on [low, high]."""
    f_low = function(low)
    for _ in range(iterations):
        middle = (low + high) / 2
        f_middle = function(middle)
        if abs(f_middle) < tolerance or high - low < tolerance:
            return middle
        if (f_middle > 0) == (f_low > 0):
            low, f_low = middle, f_middle
        else:
            high = middle
    return (low + high) / 2


def multiplicative(odds):
    _check(odds)
    raw = implied(odds)
    total = sum(raw)
    return raw[0] / total, raw[1] / total


def additive(odds):
    """Equal deduction from both sides. Can go below zero for a very long price; it is then clipped to (0, 1)."""
    _check(odds)
    raw = implied(odds)
    cut = (sum(raw) - 1.0) / 2
    first = min(max(raw[0] - cut, 1e-9), 1 - 1e-9)
    return first, 1.0 - first


def power(odds):
    _check(odds)
    raw = implied(odds)
    if abs(sum(raw) - 1.0) < 1e-15:
        return raw
    k = _bisect(lambda k: raw[0] ** k + raw[1] ** k - 1.0, 1e-6, 50.0)
    first = raw[0] ** k
    return first, 1.0 - first


def shin(odds):
    """Shin's insider-trading model for two outcomes: p_i = (sqrt(z^2 + 4 (1 - z) r_i^2 / S) - z) / (2 (1 - z)),
    with r_i = 1 / o_i, S their sum, and the insider share z chosen so the p_i sum to 1."""
    _check(odds)
    raw = implied(odds)
    total = sum(raw)
    if total <= 1.0:
        return raw[0] / total, raw[1] / total

    def probabilities(z):
        return [(math.sqrt(z * z + 4 * (1 - z) * r * r / total) - z) / (2 * (1 - z)) for r in raw]

    z = _bisect(lambda z: sum(probabilities(z)) - 1.0, 0.0, 0.999)
    first = probabilities(z)[0]
    return first, 1.0 - first


def fair(odds, method="multiplicative"):
    """Margin-free probabilities (player 1, player 2) by the named method."""
    return {"multiplicative": multiplicative, "additive": additive, "power": power, "shin": shin}[method](odds)


def expected_value(p, o):
    """Expected net return per unit staked at decimal price o when the win probability is p: p * o - 1."""
    return p * o - 1.0


def kelly_fraction(p, o):
    """The Kelly stake as a share of bankroll, (p * o - 1) / (o - 1), or 0 when the expected value is not positive."""
    return max(expected_value(p, o) / (o - 1.0), 0.0)

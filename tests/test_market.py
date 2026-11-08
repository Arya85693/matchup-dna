"""Phase 5: odds arithmetic (matchup_dna.market)."""
import unittest

from matchup_dna import market


class MarginTests(unittest.TestCase):
    def test_implied_probabilities_and_overround(self):
        self.assertEqual(market.implied((2.0, 4.0)), (0.5, 0.25))
        self.assertAlmostEqual(market.overround((1.9, 1.9)), 2 / 1.9)

    def test_every_method_returns_two_probabilities_summing_to_one(self):
        for odds in ((1.9, 1.9), (1.25, 4.0), (1.02, 15.0), (3.1, 1.36)):
            for method in market.METHODS:
                p = market.fair(odds, method)
                self.assertAlmostEqual(sum(p), 1.0, places=9, msg=(odds, method))
                self.assertTrue(0 < p[0] < 1 and 0 < p[1] < 1)

    def test_equal_prices_give_one_half_by_every_method(self):
        for method in market.METHODS:
            self.assertAlmostEqual(market.fair((1.87, 1.87), method)[0], 0.5, places=9)

    def test_fair_prices_are_left_alone(self):
        for method in market.METHODS:
            p = market.fair((1.25, 5.0), method)
            self.assertAlmostEqual(p[0], 0.8, places=9)

    def test_power_and_shin_put_more_of_the_margin_on_the_longshot(self):
        odds = (1.25, 4.0)
        base = market.multiplicative(odds)[0]
        self.assertGreater(market.power(odds)[0], base)
        self.assertGreater(market.shin(odds)[0], base)
        self.assertGreater(market.additive(odds)[0], base)

    def test_swapping_the_players_swaps_the_probabilities(self):
        for method in market.METHODS:
            a = market.fair((1.4, 3.05), method)
            b = market.fair((3.05, 1.4), method)
            self.assertAlmostEqual(a[0], b[1], places=9)

    def test_impossible_prices_are_refused(self):
        for odds in ((1.0, 2.0), (None, 2.0), (2.0,)):
            with self.assertRaises(ValueError):
                market.multiplicative(odds)


class ValueTests(unittest.TestCase):
    def test_expected_value_is_p_times_odds_minus_one(self):
        self.assertAlmostEqual(market.expected_value(0.55, 2.0), 0.10)
        self.assertAlmostEqual(market.expected_value(0.5, 2.0), 0.0)

    def test_kelly_stake(self):
        self.assertAlmostEqual(market.kelly_fraction(0.55, 2.0), 0.10)
        self.assertEqual(market.kelly_fraction(0.45, 2.0), 0.0)  # no stake without a positive expected value


if __name__ == "__main__":
    unittest.main()

"""Phase 5: paper backtests (matchup_dna.backtest). Simulated decisions only."""
import unittest

from matchup_dna import backtest


def row(i, p_model, open_a, open_b, a_won, close=(None, None), p_market=0.5):
    return {"match_id": f"m{i}", "start": f"2024-01-{i + 1:02d} 12:00:00", "tourney_date": 20240101 + i,
            "a_won": a_won, "open_a": open_a, "open_b": open_b, "close_a": close[0], "close_b": close[1],
            "p_model": p_model, "p_market": p_market}


class DecideTests(unittest.TestCase):
    def test_backs_the_side_with_the_larger_expected_value_above_the_threshold(self):
        self.assertEqual(backtest.decide(0.6, 2.0, 2.0, 0.05)[0], 0)      # EV +0.20 on A
        self.assertEqual(backtest.decide(0.4, 2.0, 2.0, 0.05)[0], 1)      # EV +0.20 on B
        self.assertIsNone(backtest.decide(0.51, 1.95, 1.95, 0.05)[0])     # EV below the threshold

    def test_at_fair_market_prices_with_a_margin_neither_side_has_value(self):
        self.assertIsNone(backtest.decide(0.5, 1.93, 1.93, 0.0)[0])


class RunTests(unittest.TestCase):
    def test_flat_profit_drawdown_and_losing_run(self):
        rows = [row(0, 0.7, 2.0, 2.0, 1), row(1, 0.7, 2.0, 2.0, 0), row(2, 0.7, 2.0, 2.0, 0), row(3, 0.7, 2.0, 2.0, 1)]
        bets, m = backtest.run(rows, lambda r: r["p_model"], 0.05)
        self.assertEqual([b["profit"] for b in bets], [1.0, -1.0, -1.0, 1.0])
        self.assertEqual((m["bets"], m["profit"], m["roi"]), (4, 0.0, 0.0))
        self.assertEqual(m["max_drawdown"], 2.0)
        self.assertEqual(m["longest_losing_run"], 2)

    def test_a_haircut_shrinks_winnings_only(self):
        bets, _ = backtest.run([row(0, 0.7, 2.0, 2.0, 1), row(1, 0.7, 2.0, 2.0, 0)], lambda r: r["p_model"], 0.05,
                               haircut=0.10)
        self.assertAlmostEqual(bets[0]["profit"], 0.9)
        self.assertEqual(bets[1]["profit"], -1.0)

    def test_kelly_stakes_a_capped_share_of_the_bankroll(self):
        bets, m = backtest.run([row(0, 0.9, 2.0, 2.0, 0)], lambda r: r["p_model"], 0.05, sizing="kelly")
        self.assertAlmostEqual(bets[0]["stake"], 0.02)       # quarter Kelly would be 0.2; the cap is 2%
        self.assertAlmostEqual(m["final_bankroll"], 0.98)
        self.assertAlmostEqual(m["max_drawdown"], 0.02)

    def test_closing_line_value_and_the_market_benchmark(self):
        bets, m = backtest.run([row(0, 0.7, 2.2, 1.7, 1, close=(2.0, 1.85), p_market=0.45)], lambda r: r["p_model"],
                               0.05)
        self.assertAlmostEqual(bets[0]["clv"], 2.2 / 2.0 - 1)
        self.assertAlmostEqual(m["expected_roi_if_market_right"], 0.45 * 2.2 - 1)

    def test_bets_are_settled_in_order_of_start_time(self):
        rows = [row(1, 0.7, 2.0, 2.0, 0), row(0, 0.7, 2.0, 2.0, 1)]
        bets, _ = backtest.run(rows, lambda r: r["p_model"], 0.05)
        self.assertEqual([b["match_id"] for b in bets], ["m0", "m1"])


if __name__ == "__main__":
    unittest.main()

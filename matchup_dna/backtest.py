"""Paper backtests for Phase 5. Simulated decisions only: nothing here places, or is meant to place, a real bet.

A rule sees, for each match in order of start time, a decision probability that player A wins and the two opening
decimal prices. It backs the side whose expected value p * o - 1 (brief section 30) is at least a threshold, at
most one side per match. With a bookmaker margin both sides can never have positive expected value at once under
the market's own probabilities, so any bet is a bet that the decision probability is better than the price.

Costs. The opening price already contains the bookmaker's margin. An optional haircut shrinks each price's net
return, o -> 1 + (o - 1)(1 - haircut), to stand for a worse price than the one recorded (slippage, a softer book).

Sizing. Flat: one unit per bet. Fractional Kelly: a fixed share of the Kelly fraction of the current bankroll,
capped per bet. Kelly assumes the decision probability is right; when it is not, Kelly sizing amplifies the error,
which is why the cap and the fraction are fixed in advance.
"""
from matchup_dna import market


def effective_price(odds, haircut=0.0):
    return 1.0 + (odds - 1.0) * (1.0 - haircut)


def decide(p_a, odds_a, odds_b, threshold):
    """(side, expected value) for the side to back, 0 for A and 1 for B, or (None, best expected value)."""
    ev_a = market.expected_value(p_a, odds_a)
    ev_b = market.expected_value(1.0 - p_a, odds_b)
    side, ev = (0, ev_a) if ev_a >= ev_b else (1, ev_b)
    return (side if ev >= threshold else None), ev


def run(rows, probability, threshold, sizing="flat", kelly_share=0.25, cap=0.02, haircut=0.0):
    """rows: dicts with start (sortable), a_won, open_a, open_b, p_market (A's margin-free opening probability), and
    optionally close_a, close_b; probability(row) is the decision probability for A. Returns the bets and metrics."""
    bets, bankroll = [], 1.0
    for row in sorted(rows, key=lambda r: (r["start"], r["match_id"])):
        p = probability(row)
        side, ev = decide(p, row["open_a"], row["open_b"], threshold)
        if side is None:
            continue
        odds = row["open_a"] if side == 0 else row["open_b"]
        price = effective_price(odds, haircut)
        p_side = p if side == 0 else 1 - p
        won = bool(row["a_won"]) == (side == 0)
        if sizing == "flat":
            stake = 1.0
        else:
            stake = min(cap, kelly_share * market.kelly_fraction(p_side, price)) * bankroll
        profit = stake * (price - 1.0) if won else -stake
        bankroll += profit if sizing != "flat" else 0.0
        p_market_side = row["p_market"] if side == 0 else 1 - row["p_market"]
        close = (row.get("close_a"), row.get("close_b"))
        bets.append({"match_id": row["match_id"], "start": row["start"], "side": side, "odds": odds, "price": price,
                     "p": p_side, "ev": ev, "stake": stake, "won": won, "profit": profit, "bankroll": bankroll,
                     "expected_if_market_right": stake * (p_market_side * price - 1.0),
                     "clv": (odds / close[side] - 1.0) if None not in close else None,
                     "tourney_date": row["tourney_date"]})
    return bets, metrics(bets, sizing)


def metrics(bets, sizing="flat"):
    staked = sum(b["stake"] for b in bets)
    profit = sum(b["profit"] for b in bets)
    running = peak = 0.0 if sizing == "flat" else 1.0  # units of profit, or the bankroll starting at 1
    drawdown = 0.0
    losing = longest = 0
    for b in bets:
        running = b["bankroll"] if sizing != "flat" else running + b["profit"]
        peak = max(peak, running)
        drawdown = max(drawdown, (peak - running) / peak if sizing != "flat" and peak else peak - running)
        losing = 0 if b["won"] else losing + 1
        longest = max(longest, losing)
    clv = [b["clv"] for b in bets if b["clv"] is not None]
    return {"bets": len(bets), "staked": staked, "profit": profit, "roi": profit / staked if staked else float("nan"),
            "hit_rate": sum(b["won"] for b in bets) / len(bets) if bets else float("nan"),
            "mean_odds": sum(b["odds"] for b in bets) / len(bets) if bets else float("nan"),
            "max_drawdown": drawdown, "longest_losing_run": longest,
            "expected_roi_if_market_right": (sum(b["expected_if_market_right"] for b in bets) / staked) if staked else float("nan"),
            "final_bankroll": bets[-1]["bankroll"] if bets and sizing != "flat" else None,
            "clv_bets": len(clv), "mean_clv": sum(clv) / len(clv) if clv else float("nan"),
            "share_beating_close": sum(c > 0 for c in clv) / len(clv) if clv else float("nan")}

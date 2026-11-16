/**
 * Historical research figures (Phases 2-5), from web/content/research, written by `python -m web.publisher.research`.
 * That export recomputes or reads each figure from the saved results and refuses to write unless every headline equals
 * the published report. Validated again here; nothing is recomputed in the browser or on the server.
 */
import { z } from "zod";
import historicalJson from "@/content/research/historical.json";
import marketJson from "@/content/research/market.json";
import bigMatchJson from "@/content/research/big-match.json";

const Scores = z.object({ n: z.number(), log_loss: z.number(), brier: z.number(), accuracy: z.number() });
const Bin = z.object({
  low: z.number(), high: z.number(), n: z.number(), mean_p: z.number(), observed: z.number(),
  observed_low: z.number(), observed_high: z.number(),
});
const Gap = z.object({ rows: z.number(), gap: z.number(), se: z.number(), low: z.number(), high: z.number(), p: z.number() });
const Source = z.object({ file: z.string(), sha256: z.string() });

const Historical = z.object({
  schema_version: z.literal("1"),
  phase2: z.object({
    window: z.string(),
    ATP: z.object({ n: z.number(), elo: z.number(), surface_elo: z.number(), accuracy_surface_elo: z.number() }),
    WTA: z.object({ n: z.number(), elo: z.number(), surface_elo: z.number(), accuracy_surface_elo: z.number() }),
  }),
  phase3: z.object({
    model: Scores, benchmark: Scores, by_tour: z.record(z.string(), Scores), reliability: z.array(Bin), source: Source,
  }),
  phase4: z.object({
    held_out_original: z.object({ scores: Scores, p3_gap: Gap }),
    held_out_corrected: z.object({ scores: Scores, p3: Scores, p3_gap: Gap, reliability: z.array(Bin) }),
    round_aware_original: Gap,
    round_aware_corrected: Gap,
    long_run_by_year: z.array(z.object({ year: z.number(), phase4: Scores, elo: Scores })),
    sources: z.array(Source),
  }),
});

const MarketGap = z.looseObject({
  matches: z.number(), gap: z.number(), se: z.number().nullable(), low: z.number().nullable(),
  high: z.number().nullable(), p: z.number().nullable(),
});
const MarketScores = z.object({ matches: z.number(), log_loss: z.number(), brier: z.number(), accuracy: z.number() });

const Market = z.object({
  schema_version: z.literal("1"),
  matches: z.number(),
  window: z.string(),
  scores: z.record(z.string(), MarketScores),
  gaps: z.record(z.string(), MarketGap),
  information_slope: z.object({ b: z.number(), se: z.number(), low: z.number(), high: z.number(), p: z.number() }),
  by_year: z.record(z.string(), MarketGap),
  by_tour: z.record(z.string(), MarketGap),
  by_ranking: z.record(z.string(), MarketGap),
  closing: z.record(z.string(), MarketGap),
  backtests: z.record(z.string(), z.object({
    bets: z.number(), roi: z.number(), roi_interval: z.tuple([z.number(), z.number()]).nullable(),
    hit_rate: z.number().nullable(), mean_odds: z.number().nullable(),
    expected_roi_if_market_right: z.number().nullable(), share_beating_close: z.number().nullable(),
    final_bankroll: z.number().nullable(),
  })),
  source: Source,
});

export const HISTORICAL = Historical.parse(historicalJson);
export const MARKET = Market.parse(marketJson);
export type ReliabilityBin = z.infer<typeof Bin>;

/** Short figures used on the homepage, taken from the validated exports above. */
export const HEADLINES = {
  marketLogLoss: MARKET.scores["opening market"]!.log_loss,
  modelLogLoss: MARKET.scores["Phase 4"]!.log_loss,
  marketMatches: MARKET.matches,
  marketWindow: MARKET.window,
  paperRoi: MARKET.backtests["primary"]!.roi,
  heldOutLogLoss: HISTORICAL.phase4.held_out_corrected.scores.log_loss,
  heldOutMatches: HISTORICAL.phase4.held_out_corrected.scores.n,
};

/** The post-hoc myth check (docs/Myth Check - Do Players Choke in Big Matches.md). Aggregates only. */
const Interval = z.object({ r: z.number(), low: z.number(), high: z.number() });
const BigForecast = z.object({
  matches: z.number(), with_history: z.number(), beta: z.number(), se: z.number(), log_loss_change: z.number(), permutation_p: z.number(),
});
const Fit = z.object({ beta: z.number(), se: z.number(), p: z.number() });
const Robustness = z.object({
  sims: z.object({ null: z.number(), power: z.number(), permutations: z.number(), game_permutations: z.number() }),
  slope_tests: z.array(z.object({
    tour: z.string(), best_of: z.number(), big: z.number(), big_se: z.number(), regular: z.number(), regular_se: z.number(), z: z.number(), p: z.number(),
  })),
  null: z.array(z.object({ tour: z.string(), test: z.string(), observed: z.number(), critical: z.number(), p: z.number() })),
  holm: z.array(z.object({ tour: z.string(), set: z.string(), p: z.number() })),
  power: z.object({
    taus: z.array(z.number()), evens: z.array(z.number()),
    rows: z.array(z.object({ tour: z.string(), test: z.string(), power: z.array(z.number()), bound: z.number().nullable(), bound_points: z.number().nullable() })),
  }),
  games: z.array(z.object({
    tour: z.string(), matches: z.number(), per_match_sd: z.number(),
    spread: z.array(z.object({ set: z.string(), players: z.number(), ratio: z.number(), trait_sd: z.number(), p: z.number() })),
    clutch: z.object({ players: z.number(), ratio: z.number(), p: z.number() }),
    split_half: Interval.extend({ players: z.number() }),
    players: z.number(),
    correlations: z.object({ big: Interval, clutch: Interval, regular: Interval }),
    forecasts: z.object({ big: Fit, clutch: Fit }),
  })),
  within: z.array(z.object({
    tour: z.string(), eligible: z.number(), spread: z.record(z.string(), z.number()), clutch: z.number(), split_half: Interval,
    correlations: z.object({ big: z.number(), clutch: z.number() }), forecasts: z.object({ big: Fit, clutch: Fit }),
  })),
  sensitivity: z.array(z.object({
    tour: z.string(), label: z.string(), players: z.number(), clutch_r: z.number(), clutch_low: z.number(), clutch_high: z.number(),
    big_beta: z.number(), big_p: z.number(), clutch_beta: z.number(), clutch_p: z.number(),
  })),
  format: z.array(z.object({
    tour: z.string(), best_of: z.number(), big_matches: z.number(), regular_matches: z.number(),
    wins: z.object({ players: z.number(), ratio: z.number(), p: z.number() }),
    games: z.object({ players: z.number(), ratio: z.number(), p: z.number() }),
  })),
  sources: z.array(Source),
});
const PeriodRecord = z.object({ big: z.number(), won: z.number(), expected: z.number(), score: z.number(), clutch: z.number() });
const PlayerRecord = z.object({ name: z.string(), early: PeriodRecord, late: PeriodRecord });
const Shift = z.object({ early: z.number(), late: z.number() });
const Players = z.object({
  tours: z.array(z.object({
    tour: z.string(), players: z.number(), shown: z.number(), top: z.array(PlayerRecord), bottom: z.array(PlayerRecord),
    means: z.record(z.string(), z.object({ score: Shift, clutch: Shift })),
    top_still_positive: z.number(), bottom_still_negative: z.number(),
  })),
  sources: z.array(Source),
});
const BigMatch = z.object({
  schema_version: z.literal("2"),
  evidence: z.literal("post-hoc"),
  robustness: Robustness,
  players: Players,
  window: z.string(), matches: z.number(), big_matches: z.number(), shrink: z.number(), min_big: z.number(),
  periods: z.tuple([z.string(), z.string()]),
  calibration: z.array(z.object({ tour: z.string(), kind: z.enum(["big", "regular"]), best_of: z.number(), slope: z.number() })),
  spread: z.array(z.object({
    tour: z.string(), set: z.string(), players: z.number(), ratio: z.number(), observed_sd: z.number(), noise_sd: z.number(),
    trait_sd: z.number(), implied_k: z.number().nullable(),
  })),
  split_half: z.record(z.string(), Interval.extend({ players: z.number(), spearman_brown: z.number() })),
  period_split: z.record(z.string(), z.object({
    players: z.number(),
    correlations: z.object({ "big-match": Interval, clutch: Interval, "regular-match": Interval }),
    forecasts: z.object({ "big-match": BigForecast, clutch: BigForecast }),
  })),
  streak: z.object({ finals: z.number(), p_win: z.number(), two: z.number(), three: z.number() }),
  sources: z.array(Source),
});

export const BIG_MATCH = BigMatch.parse(bigMatchJson);
export type BigMatchResearch = typeof BIG_MATCH;

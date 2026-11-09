/**
 * Historical research figures (Phases 2-5), from web/content/research, written by `python -m web.publisher.research`.
 * That export recomputes or reads each figure from the saved results and refuses to write unless every headline equals
 * the published report. Validated again here; nothing is recomputed in the browser or on the server.
 */
import { z } from "zod";
import historicalJson from "@/content/research/historical.json";
import marketJson from "@/content/research/market.json";

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

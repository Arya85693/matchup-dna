/**
 * The snapshot contract, validated when a file is read. A file that fails is treated as unavailable (an error state),
 * never partly rendered. The publisher checks the same rules before writing (web/publisher/contract.py).
 */
import { z } from "zod";

const UtcTime = z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/, "UTC time like 2026-11-09T05:30:00Z");
const Probability = z.number().gt(0).lt(1);
const Pair = z
  .tuple([Probability, Probability])
  .refine(([a, b]) => Math.abs(a + b - 1) < 1e-9, "the two probabilities must sum to 1");

export const PlayerSchema = z.object({
  id: z.number().int().nullable(),
  name: z.string().nullable(),
  rank: z.number().int().nullable(),
  rank_as_of: z.string().nullable(),
  seed: z.number().int().nullable(),
  identity: z.string().nullable(),
});

const AvailableForecast = z.object({
  available: z.literal(true),
  model_version: z.string(),
  prediction_id: z.string(),
  issued_at: UtcTime,
  p: Pair,
  counted: z.boolean(),
  revision: z.object({ prediction_id: z.string(), issued_at: UtcTime, p: Pair }).nullable(),
});

// strict(): an unavailable forecast that carried a number would fail here.
const UnavailableForecast = z
  .object({
    available: z.literal(false),
    model_version: z.string(),
    decision: z.string().nullable(),
    reason_code: z.string(),
    reason: z.string(),
  })
  .strict();

export const ForecastSchema = z.discriminatedUnion("available", [AvailableForecast, UnavailableForecast]);

export const MatchStateSchema = z.enum([
  "scheduled", "time_tbc", "in_progress", "postponed", "suspended", "cancelled", "result_pending",
  "result_conflict", "completed", "retired", "walkover",
]);

export const MatchSummarySchema = z.object({
  uid: z.string().regex(/^M-[0-9a-f]+$/),
  tour: z.enum(["ATP", "WTA"]),
  round: z.string(),
  best_of: z.number().int().nullable(),
  edition: z.object({
    uid: z.string(),
    name: z.string(),
    level: z.string().nullable(),
    surface: z.string().nullable(),
    start_date: z.string(),
  }),
  start: UtcTime.nullable(),
  state: MatchStateSchema,
  players: z.tuple([PlayerSchema, PlayerSchema]),
  forecasts: z.object({ tournament_start: ForecastSchema, round_aware: ForecastSchema }),
  result: z
    .object({ status: z.string(), winner_index: z.number().int().nullable(), score: z.string().nullable() })
    .nullable(),
});

export const MatchIndexSchema = z.object({
  schema_version: z.literal("1"),
  generated_at: UtcTime,
  matches: z.array(MatchSummarySchema),
});

const InputValue = z.number().nullable();

export const VersionSchema = z.object({
  prediction_id: z.string(),
  issued_at: UtcTime,
  scheduled_start: UtcTime.nullable(),
  p: Pair,
  counted: z.boolean(),
  supersedes: z.string().nullable(),
  log_odds: z.number(),
  contributions: z.array(z.object({ feature: z.string(), log_odds: z.number() })),
  inputs: z.tuple([z.record(z.string(), InputValue), z.record(z.string(), InputValue)]),
  rank_source_dates: z.tuple([z.string().nullable(), z.string().nullable()]),
  integrity: z.object({
    input_sha256: z.string(),
    model_sha256: z.string(),
    code_sha256: z.string().nullable(),
    code_matches_protocol: z.boolean(),
    record_hash: z.string(),
    ledger_position: z.number().int(),
  }),
});

export const MatchPageSchema = z.object({
  schema_version: z.literal("1"),
  generated_at: UtcTime,
  match: MatchSummarySchema,
  versions: z.object({ tournament_start: z.array(VersionSchema), round_aware: z.array(VersionSchema) }),
  decisions: z.array(
    z.object({
      model_version: z.string(),
      kind: z.string(),
      decision: z.string(),
      code: z.string(),
      text: z.string(),
      first_at: UtcTime,
      last_at: UtcTime,
      times: z.number().int(),
    }),
  ),
  outcomes: z.array(
    z.object({
      source: z.string(),
      status: z.string(),
      score: z.string().nullable(),
      winner_index: z.number().int().nullable(),
      retrieved_at: UtcTime,
    }),
  ),
});

const Freshness = z.object({ last: UtcTime.nullable(), hours_ago: z.number().nullable() });

export const StatusSchema = z.object({
  schema_version: z.literal("1"),
  generated_at: UtcTime,
  ok: z.boolean(),
  fresh: z.boolean(),
  freshness: z.object({ forecast: Freshness, settle: Freshness, espn_download: Freshness }),
  stale_after_hours: z.number(),
  rule: z.string(),
  failed_runs_last_7_days: z.number().int(),
  counts: z.object({
    forecasts: z.number().int(),
    matches: z.number().int(),
    settled: z.number().int(),
    result_conflicts: z.number().int(),
  }),
  integrity: z.object({ ok: z.boolean(), problems: z.number().int(), check: z.string() }),
});

const Metrics = z.looseObject({ n: z.number().int() });

export const TrackRecordSchema = z.object({
  schema_version: z.literal("1"),
  generated_at: UtcTime,
  interim: z.literal(true),
  label: z.string(),
  protocol: z.object({
    name: z.string(),
    frozen_at: UtcTime,
    issued_from: UtcTime,
    scheduled_up_to: UtcTime,
    final_evaluation_not_before: UtcTime,
    counted_forecast: z.string(),
    counted_matches: z.string(),
    reporting_rule: z.string(),
    code_sha256: z.string(),
  }),
  counts: z.object({
    issued: z.record(z.string(), z.number().int()),
    counted: z.record(z.string(), z.number().int()),
    scored: z.record(z.string(), z.number().int()),
    excluded: z.array(z.object({ reason: z.string(), n: z.number().int() })),
  }),
  tournament_start: z.object({ all: Metrics, ATP: Metrics, WTA: Metrics, surface_elo_benchmark: Metrics }),
  round_aware: z.object({ all: Metrics }),
  round_aware_minus_tournament_start: Metrics,
  tournament_start_on_same_matches: Metrics,
});

export const ManifestSchema = z.object({
  schema_version: z.literal("1"),
  publisher_version: z.string(),
  generated_at: UtcTime,
  snapshot: z.string().regex(/^\d{8}T\d{6}Z$/),
  files: z.record(z.string(), z.string().regex(/^[0-9a-f]{64}$/)),
  ledger: z.object({ count: z.number().int(), head: z.string().nullable() }),
  code_matches_protocol: z.boolean(),
});

export const ModelsSchema = z.object({
  schema_version: z.literal("1"),
  models: z.array(
    z.object({
      model_version: z.string(),
      kind: z.enum(["tournament_start", "round_aware"]),
      artifact_sha256: z.string(),
      registered_at: z.string(),
      label: z.string(),
      uses: z.array(z.string()),
      does_not_use: z.array(z.string()),
      applies_to: z.string().optional(),
      features: z.record(z.string(), z.array(z.string())),
      fit: z.object({ from: z.number(), rule: z.string(), through_week: z.number() }).nullable(),
      population: z.string().nullable(),
    }),
  ),
});

export const LedgerSchema = z.object({
  schema_version: z.literal("1"),
  count: z.number().int(),
  head: z.string().nullable(),
  entries: z.array(
    z.object({
      position: z.number().int(),
      prediction_id: z.string(),
      match_uid: z.string(),
      model_version: z.string(),
      issued_at: UtcTime,
      record_hash: z.string(),
    }),
  ),
});

export const ArchiveSchema = z.object({
  schema_version: z.literal("1"),
  generated_at: UtcTime,
  entries: z.array(z.object({
    prediction_id: z.string(),
    match_uid: z.string(),
    model_version: z.string(),
    kind: z.enum(["tournament_start", "round_aware"]),
    issued_at: UtcTime,
    scheduled_start: UtcTime.nullable(),
    p: Pair,
    players: z.tuple([z.string().nullable(), z.string().nullable()]),
    tour: z.enum(["ATP", "WTA"]),
    event: z.string(),
    round: z.string(),
    counted: z.boolean(),
    superseded: z.boolean(),
    result_status: z.string().nullable(),
    favourite_won: z.boolean().nullable(),
    record_hash: z.string(),
    ledger_position: z.number().int(),
    supersedes: z.string().nullable(),
    issued_before_start: z.boolean(),
    settled_at: UtcTime.nullable(),
    result_state: z.enum(["settled", "conflict"]).nullable(),
    features: z.record(z.string(), z.number()),
    contributions: z.array(z.tuple([z.string(), z.number()])),
    integrity: z.object({
      input_sha256: z.string(), model_sha256: z.string(), code_sha256: z.string().nullable(), code_matches_protocol: z.boolean(),
    }),
  })),
});

const ProfileInputs = z.object({
  elo: z.number().nullable(), surface_elo: z.number().nullable(), rank: z.number().nullable(),
  serve_points_won: z.number().nullable(), return_points_won: z.number().nullable(), form: z.number().nullable(),
  elo_matches: z.number().nullable(), days_since_last_match: z.number().nullable(),
});

export const PlayersSchema = z.object({
  schema_version: z.literal("1"),
  generated_at: UtcTime,
  players: z.array(z.object({
    id: z.number().int(),
    name: z.string().nullable(),
    tour: z.enum(["ATP", "WTA"]),
    latest: z.object({
      issued_at: UtcTime, surface: z.string().nullable(), rank_as_of: z.string().nullable(),
      identity: z.string().nullable(), inputs: ProfileInputs,
    }),
    matches: z.array(z.object({
      match_uid: z.string(), start: UtcTime.nullable(), event: z.string(), surface: z.string().nullable(),
      round: z.string(), opponent: z.string().nullable(), p: Probability, issued_at: UtcTime,
      outcome: z.enum(["won", "lost"]).nullable(),
    })),
  })),
});

const WinLoss = z.tuple([z.number().int(), z.number().int()]);
const SURFACE_KEYS = ["Hard", "Clay", "Grass"] as const;

export const HistoryIndexSchema = z.object({
  schema_version: z.literal("1"),
  generated_at: UtcTime,
  players: z.array(z.object({
    id: z.number().int(), tour: z.enum(["ATP", "WTA"]), name: z.string(), photo: z.string().url().nullable(), elo: z.number(), elo_rank: z.number().int(), elo_change_90d: z.number().nullable(),
    last_match: z.string(), rated_matches: z.number().int(), surfaces: z.record(z.enum(SURFACE_KEYS), z.number()),
    season: WinLoss, spark: z.array(z.tuple([z.string(), z.number()])),
    surface_matches: z.record(z.enum(SURFACE_KEYS), z.number().int()),
  })),
});

export const HistoryPlayerSchema = z.object({
  schema_version: z.literal("1"),
  generated_at: UtcTime,
  player: z.object({
    id: z.number().int(), tour: z.enum(["ATP", "WTA"]), name: z.string(), photo: z.string().url().nullable(), elo: z.number(), elo_rank: z.number().int(), rated_matches: z.number().int(),
    /** Set for freely licensed (Wikimedia Commons) photos, which must be credited. */
    photo_credit: z.object({
      author: z.string(), license: z.string(), license_url: z.string().url().nullable(), source: z.string().url(),
    }).nullable().default(null),
    elo_change_90d: z.number().nullable(), last_match: z.string(),
    surfaces: z.record(z.enum(SURFACE_KEYS), z.object({ elo: z.number(), matches: z.number().int() })),
    season: z.object({ year: z.number().int(), All: WinLoss, Hard: WinLoss, Clay: WinLoss, Grass: WinLoss }),
    series: z.array(z.tuple([z.string(), z.number()])),
    recent: z.array(z.object({
      date: z.string(), event: z.string(), round: z.string(), surface: z.string().nullable(),
      opponent_id: z.number().int(), opponent: z.string(), won: z.boolean(),
    })),
    /** Meetings with each other active player on the same tour, newest first; keys are opponent ids. */
    h2h: z.record(z.string().regex(/^-?\d{1,18}$/), z.array(z.object({
      date: z.string(), event: z.string(), round: z.string(), surface: z.string().nullable(), won: z.boolean(), retired: z.boolean(),
    }))).default({}),
  }),
});

export const HistoryManifestSchema = z.object({
  schema_version: z.literal("1"), generated_at: UtcTime, snapshot: z.string().regex(/^\d{8}T\d{6}Z$/),
  files: z.record(z.string(), z.string().regex(/^[0-9a-f]{64}$/)), players: z.number().int().optional(),
});

export type HistoryIndex = z.infer<typeof HistoryIndexSchema>;
export type HistoryListing = HistoryIndex["players"][number];
export type HistoryPlayer = z.infer<typeof HistoryPlayerSchema>["player"];
export type Archive = z.infer<typeof ArchiveSchema>;
export type ArchiveEntry = Archive["entries"][number];
export type Players = z.infer<typeof PlayersSchema>;
export type PlayerProfile = Players["players"][number];
export type Models = z.infer<typeof ModelsSchema>;
export type Ledger = z.infer<typeof LedgerSchema>;
export type Player = z.infer<typeof PlayerSchema>;
export type Forecast = z.infer<typeof ForecastSchema>;
export type AvailableForecast = z.infer<typeof AvailableForecast>;
export type MatchState = z.infer<typeof MatchStateSchema>;
export type MatchSummary = z.infer<typeof MatchSummarySchema>;
export type MatchIndex = z.infer<typeof MatchIndexSchema>;
export type Version = z.infer<typeof VersionSchema>;
export type MatchPage = z.infer<typeof MatchPageSchema>;
export type Status = z.infer<typeof StatusSchema>;
export type TrackRecord = z.infer<typeof TrackRecordSchema>;
export type Manifest = z.infer<typeof ManifestSchema>;


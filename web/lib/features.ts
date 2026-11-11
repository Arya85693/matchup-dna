/**
 * Plain-language names for the models' inputs (the stored feature keys in models/*.json) and for the stored input
 * values shown on a match page. Wording only; the values themselves come from the snapshot.
 */

export const FEATURES: Record<string, { label: string; help: string }> = {
  elo_x_tier: { label: "Elo x event tier", help: "ITF model only: how much more, or less, rating matters at stronger ITF events." },
  elo_logit: { label: "Overall Elo", help: "Strength rating from every past result, weighted by the opponent's strength." },
  surface_elo_logit: { label: "Elo on this surface", help: "The same rating, built from matches on this surface." },
  log_rank_diff: { label: "Ranking", help: "The official ranking before the match (on a log scale)." },
  rank_missing_diff: { label: "Unranked", help: "A player without a ranking." },
  log_days_since_diff: { label: "Time since last match", help: "Days since each player last played (on a log scale)." },
  form_diff: { label: "Recent form", help: "Recent results compared with what Elo expected." },
  serve_diff: { label: "Serve", help: "Share of service points won, adjusted for the opponents faced." },
  return_diff: { label: "Return", help: "Share of return points won, adjusted for the opponents faced." },
  no_stats_diff: { label: "Missing serve data", help: "No serve and return statistics on record." },
  ra_elo_shift_logit: { label: "Elo gained this tournament", help: "Change in Elo from this tournament's earlier rounds." },
  ra_surface_elo_shift_logit: {
    label: "Surface Elo gained this tournament", help: "Change in surface Elo from this tournament's earlier rounds.",
  },
  ra_dominance_diff: { label: "Games won this tournament", help: "Share of games won in this tournament's earlier rounds." },
};

export function featureLabel(key: string): string {
  return FEATURES[key]?.label ?? key;
}

type InputFormat = (v: number) => string;
const whole: InputFormat = (v) => Math.round(v).toLocaleString("en-GB");
const share: InputFormat = (v) => `${(v * 100).toFixed(1)}%`;
const signed: InputFormat = (v) => `${v > 0 ? "+" : ""}${Math.round(v)}`;
const form: InputFormat = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(0)} pts`;

export const INPUTS: { key: string; label: string; format: InputFormat; help?: string; roundAware?: boolean }[] = [
  { key: "elo", label: "Overall Elo", format: whole },
  { key: "surface_elo", label: "Surface Elo", format: whole, help: "Blended with overall Elo, as the model uses it" },
  { key: "rank", label: "Ranking", format: whole },
  { key: "days_since_last_match", label: "Days since last match", format: whole },
  { key: "form", label: "Recent form", format: form,
    help: "Average of (result minus Elo's expected score) over the last 10 rated matches, in percentage points" },
  { key: "serve_points_won", label: "Service points won", format: share, help: "Opponent-adjusted estimate" },
  { key: "return_points_won", label: "Return points won", format: share, help: "Opponent-adjusted estimate" },
  { key: "elo_matches", label: "Rated matches on record", format: whole },
  { key: "matches_this_event", label: "Matches this tournament", format: whole, roundAware: true },
  { key: "games_won_share_this_event", label: "Games won this tournament", format: share, roundAware: true },
  { key: "elo_change_this_event", label: "Elo change this tournament", format: signed, roundAware: true },
];

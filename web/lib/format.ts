/**
 * Display formatting. Pure functions with no imports, so the Node test runner can load this file directly.
 * Nothing here computes or alters a probability: percentages are the stored values, rounded for display only.
 */

export const ROUNDS: Record<string, string> = {
  F: "Final", SF: "Semifinal", QF: "Quarterfinal", R16: "Round of 16", R32: "Round of 32", R64: "Round of 64",
  R128: "Round of 128", RR: "Round robin", BR: "Bronze medal match", ER: "Early rounds",
};

export const LEVELS: Record<string, Record<string, string>> = {
  ATP: { G: "Grand Slam", M: "Masters 1000", A: "ATP Tour", F: "ATP Finals", D: "Davis Cup", O: "Olympics" },
  WTA: { G: "Grand Slam", PM: "WTA 1000", P: "WTA 500", I: "WTA Tour", F: "WTA Finals", D: "Billie Jean King Cup", O: "Olympics" },
};

/** A player's address: ATP and WTA ids are separate pools, so the tour is part of it (e.g. atp-206173, wta--12345). */
/** A match the models never forecast because it was first seen too close to its start, under way or played. The site
 * shows these neutrally (owner's decision, 10 November 2026); the decision log keeps the exact reason. */
export function notRecorded(reasonCode: string | undefined): boolean {
  return (reasonCode ?? "").startsWith("too_late");
}
export const NOT_RECORDED_TEXT = "No pre-match forecast was recorded for this match.";

export function playerSlug(tour: string, id: number): string {
  return `${tour.toLowerCase()}-${id}`;
}

export function roundLabel(round: string): string {
  return ROUNDS[round] ?? round;
}

export function levelLabel(tour: string, level: string | null): string {
  if (!level) return tour;
  return LEVELS[tour]?.[level] ?? tour;
}

/** A stored probability as a percentage with one decimal, e.g. 0.6463 -> "64.6". */
export function pct(p: number): string {
  return (Math.round(p * 1000) / 10).toFixed(1);
}

/** Index of the favourite (higher stored probability); ties have no favourite. */
export function favourite(p: readonly [number, number]): 0 | 1 | null {
  if (p[0] === p[1]) return null;
  return p[0] > p[1] ? 0 : 1;
}

const PARTICLES = new Set(["van", "de", "da", "del", "der", "di", "le", "la", "dos", "von"]);

/** Family name for compact display: "Luca Van Assche" -> "Van Assche", "Tomas Martin Etcheverry" -> "Etcheverry". */
export function familyName(name: string | null): string {
  if (!name) return "Unknown";
  const parts = name.trim().split(/\s+/);
  let family = parts.pop() ?? name;
  while (parts.length > 1 && PARTICLES.has((parts[parts.length - 1] ?? "").toLowerCase())) {
    family = `${parts.pop()} ${family}`;
  }
  return family;
}

export const STATE_LABELS: Record<string, string> = {
  scheduled: "Scheduled", time_tbc: "Time to be confirmed", in_progress: "In progress", postponed: "Postponed",
  suspended: "Suspended", cancelled: "Cancelled", result_pending: "Result pending", result_conflict: "Result under review",
  completed: "Completed", retired: "Retirement", walkover: "Walkover",
};

/** Whether a settled match's result is scored under the protocol (completed matches only). */
export function isScoredStatus(status: string): boolean {
  return status === "completed";
}

/** "2 hours ago", "35 minutes ago", "3 days ago" from two instants. */
export function ago(fromIso: string, now: Date): string {
  const minutes = Math.max(0, Math.round((now.getTime() - Date.parse(fromIso)) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} days ago`;
}

/** Local calendar day key (YYYY-MM-DD) of an instant in a time zone. */
export function dayKey(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" })
    .formatToParts(new Date(iso));
  const get = (t: string) => parts.find((x) => x.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** A UTC calendar date in words, e.g. "9 November 2026"; used for protocol dates, which are defined in UTC. */
export function utcDate(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(iso));
}

export function shortHash(hash: string | null, length = 10): string {
  return hash ? hash.slice(0, length) : "none";
}

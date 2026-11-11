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

/** The circuit a match belongs to, always shown, so men's and women's events and every level are told apart:
 * ATP and WTA (main tour), ATP Challenger and WTA 125, ITF Men and ITF Women. `kind` is "itf" for ITF matches
 * (their level is the prize money, "15", "35", ...); otherwise the Sackmann level code decides. */
export const CIRCUITS = {
  ATP: { main: "ATP", challenger: "ATP Challenger", itf: "ITF Men" },
  WTA: { main: "WTA", challenger: "WTA 125", itf: "ITF Women" },
} as const;

export function circuitLabel(tour: string, level: string | null, kind: "main" | "itf" = "main"): string {
  const names = CIRCUITS[tour as "ATP" | "WTA"];
  if (!names) return tour;
  if (kind === "itf" || /^\d+$/.test(level ?? "")) return names.itf;      // ITF levels are prize money: "15", "35"
  return level === "C" || level === "CH" ? names.challenger : names.main;
}

/** Short level names shown after the circuit. */
export const SHORT_LEVELS: Record<string, Record<string, string>> = {
  ATP: { G: "Grand Slam", M: "Masters 1000", A: "250/500", F: "Finals", D: "Davis Cup", O: "Olympics" },
  WTA: { G: "Grand Slam", PM: "1000", P: "500", I: "250", F: "Finals", D: "Billie Jean King Cup", O: "Olympics" },
};

/** "ATP · Grand Slam", "WTA · 1000", "ITF Women · W35": the circuit first, then the event level. */
export function eventLabel(tour: string, level: string | null, kind: "main" | "itf" = "main"): string {
  const circuit = circuitLabel(tour, level, kind);
  if (kind === "itf" || /^\d+$/.test(level ?? "")) return level ? `${circuit} · ${tour === "ATP" ? "M" : "W"}${level}` : circuit;
  const named = level ? SHORT_LEVELS[tour]?.[level] : undefined;
  return named ? `${circuit} · ${named}` : circuit;
}

/** A player's address: ATP and WTA ids are separate pools, so the tour is part of it (e.g. atp-206173, wta--12345). */
/** A match the models never forecast because it was first listed too close to its start, under way or played. The
 * site shows one plain explanation for these (owner's decision, 10 November 2026); the decision log keeps the detail. */
export function notRecorded(reasonCode: string | undefined): boolean {
  return (reasonCode ?? "").startsWith("too_late");
}
export const NOT_RECORDED_TEXT = "No forecast: this match was first listed less than 30 minutes before its start, and "
  + "forecasts are only issued at least 30 minutes before play.";
export const NOT_RECORDED_SHORT = "No forecast: listed too close to the start";

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

/** A number to three significant figures with K, M or B, always rounded down, so "1.16M+" never overstates
 * (1,161,409 is 1.16M; 12,345 is 12.3K; below 1,000 the number itself). */
export function compact(value: number): string {
  const units: [number, string][] = [[1e9, "B"], [1e6, "M"], [1e3, "K"]];
  const unit = units.find(([u]) => value >= u);
  if (!unit) return String(Math.floor(value));
  const x = value / unit[0];
  const digits = x >= 100 ? 0 : x >= 10 ? 1 : 2;
  const scale = 10 ** digits;
  return `${(Math.floor(x * scale + 1e-9) / scale).toFixed(digits)}${unit[1]}`;
}

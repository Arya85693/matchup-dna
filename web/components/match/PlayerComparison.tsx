"use client";

import type { Version } from "@/lib/contract";
import { familyName } from "@/lib/format";

type Row = { key: string; label: string; fmt: (v: number) => string; better?: "high" | "low"; roundAware?: boolean; help?: string; signed?: boolean };
const ROWS: Row[] = [
  { key: "elo", label: "Elo", fmt: (v) => Math.round(v).toString(), better: "high" },
  { key: "surface_elo", label: "Surface Elo", fmt: (v) => Math.round(v).toString(), better: "high", help: "Blended with overall Elo, as the model uses it" },
  { key: "serve_points_won", label: "Service points won", fmt: (v) => `${(v * 100).toFixed(1)}%`, better: "high", help: "Opponent-adjusted estimate" },
  { key: "return_points_won", label: "Return points won", fmt: (v) => `${(v * 100).toFixed(1)}%`, better: "high", help: "Opponent-adjusted estimate" },
  { key: "form", label: "Form vs Elo", fmt: (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(0)} pts`, better: "high", help: "Results minus Elo's expectation, last 10 rated matches", signed: true },
  { key: "days_since_last_match", label: "Days since last match", fmt: (v) => Math.round(v).toString() },
  { key: "elo_matches", label: "Rated matches", fmt: (v) => Math.round(v).toLocaleString("en-GB") },
  { key: "games_won_share_this_event", label: "Games won this event", fmt: (v) => `${(v * 100).toFixed(1)}%`, better: "high", roundAware: true },
  { key: "elo_change_this_event", label: "Elo change this event", fmt: (v) => `${v > 0 ? "+" : ""}${Math.round(v)}`, better: "high", roundAware: true, signed: true },
];

/**
 * Mirrored bars: each player's stored input value, drawn from the centre outwards and scaled to the larger of the two.
 * The better value (where "better" is meaningful) is bold with a teal bar; neutral measures stay grey on both sides.
 */
export function PlayerComparison({ v, names, roundAware }: { v: Version; names: readonly [string, string]; roundAware: boolean }) {
  const rows = ROWS.filter((r) => !r.roundAware || roundAware);
  return (
    <div className="grid gap-1">
      <div className="mb-2 grid grid-cols-[minmax(0,1fr)_120px_minmax(0,1fr)] text-[12px] sm:grid-cols-[minmax(0,1fr)_150px_minmax(0,1fr)]">
        <span className="truncate font-medium">{familyName(names[0])}</span><span />
        <span className="truncate text-right font-medium">{familyName(names[1])}</span>
      </div>
      {rows.map((r) => {
        const a = v.inputs[0][r.key] ?? null, b = v.inputs[1][r.key] ?? null;
        if (a === null && b === null) return null;
        const scale = Math.max(Math.abs(a ?? 0), Math.abs(b ?? 0)) || 1;
        const aWins = r.better && a !== null && b !== null && a !== b ? (r.better === "high" ? a > b : a < b) : null;
        const bar = (value: number | null, wins: boolean | null, side: "left" | "right") => (
          <div className={`flex items-center gap-2 ${side === "left" ? "flex-row-reverse" : ""}`}>
            <div className={`flex h-2 flex-1 ${side === "left" ? "justify-end" : ""}`}>
              {value !== null && !r.signed && <span className={`anim-fill h-full rounded-sm ${wins ? "bg-accent/80" : "bg-[#3b4a5c]"}`} style={{ width: `${(Math.abs(value) / scale) * 100}%`, transformOrigin: side === "left" ? "right" : "left" }} />}
            </div>
            <span className={`fig w-14 shrink-0 text-[12px] ${side === "left" ? "text-left" : "text-right"} ${wins ? "font-semibold text-text" : "text-muted"}`}>{value === null ? "—" : r.fmt(value)}</span>
          </div>
        );
        return (
          <div key={r.key} className="grid grid-cols-[minmax(0,1fr)_120px_minmax(0,1fr)] items-center gap-x-2 rounded-md py-1.5 transition-colors hover:bg-card-hover/50 sm:grid-cols-[minmax(0,1fr)_150px_minmax(0,1fr)]" title={r.help}>
            {bar(a, aWins === true, "left")}
            <span className="text-center text-[11px] text-dim">{r.label}</span>
            {bar(b, aWins === false, "right")}
          </div>
        );
      })}
      <p className="mt-3 text-[11px] text-dim">Values stored with this forecast, as the model saw them. Bars compare the two players on each row; rows use different units, and rows that can be negative show values only.</p>
    </div>
  );
}

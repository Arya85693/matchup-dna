"use client";

import { useState } from "react";
import type { Version } from "@/lib/contract";
import { FEATURES, featureLabel } from "@/lib/features";
import { familyName, favourite, pct } from "@/lib/format";

/** Stored input values behind each feature, shown in the tooltip (ranking values are not displayed on this site). */
const INPUT_OF: Record<string, { key: string; fmt: (v: number) => string }> = {
  elo_logit: { key: "elo", fmt: (v) => Math.round(v).toString() },
  surface_elo_logit: { key: "surface_elo", fmt: (v) => Math.round(v).toString() },
  log_days_since_diff: { key: "days_since_last_match", fmt: (v) => `${Math.round(v)} days` },
  form_diff: { key: "form", fmt: (v) => `${v > 0 ? "+" : ""}${(v * 100).toFixed(0)} pts` },
  serve_diff: { key: "serve_points_won", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  return_diff: { key: "return_points_won", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  ra_dominance_diff: { key: "games_won_share_this_event", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  ra_elo_shift_logit: { key: "elo_change_this_event", fmt: (v) => `${v > 0 ? "+" : ""}${Math.round(v)}` },
  ra_surface_elo_shift_logit: { key: "surface_elo_change_this_event", fmt: (v) => `${v > 0 ? "+" : ""}${Math.round(v)}` },
};

/**
 * Diverging bars around a zero axis: each stored contribution (log-odds) pushes toward the player on that side. Teal
 * bars push toward the favourite, slate bars toward the other player. Values are the stored ones.
 */
export function ContributionChart({ v, names }: { v: Version; names: readonly [string, string] }) {
  const [active, setActive] = useState<string | null>(null);
  const shown = v.contributions.filter((c) => Math.abs(c.log_odds) >= 0.0005);
  const quiet = v.contributions.filter((c) => Math.abs(c.log_odds) < 0.0005);
  const scale = Math.max(0.2, ...shown.map((c) => Math.abs(c.log_odds)));
  const fav = favourite(v.p);
  const left = familyName(names[0]), right = familyName(names[1]);
  const current = shown.find((c) => c.feature === active);

  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-[minmax(96px,140px)_minmax(0,1fr)] gap-x-3 text-[11px] text-dim">
        <span />
        <div className="flex justify-between"><span>← favours {left}</span><span>favours {right} →</span></div>
      </div>
      <ul className="grid gap-1" onMouseLeave={() => setActive(null)}>
        {shown.map((c) => {
          const towardLeft = c.log_odds > 0;
          const toward = towardLeft ? 0 : 1;
          const width = `${(Math.abs(c.log_odds) / scale) * 44}%`;
          return (
            <li key={c.feature}>
              <button type="button" onMouseEnter={() => setActive(c.feature)} onFocus={() => setActive(c.feature)} onBlur={() => setActive(null)}
                      className={`grid w-full grid-cols-[minmax(96px,140px)_minmax(0,1fr)] items-center gap-x-3 rounded-md px-1 py-1 text-left transition-colors ${active === c.feature ? "bg-card-hover" : "hover:bg-card-hover/60"}`}>
                <span className="truncate text-[12px] text-muted">{featureLabel(c.feature)}<span className="sr-only">: {Math.abs(c.log_odds).toFixed(3)} log-odds toward {toward === 0 ? names[0] : names[1]}</span></span>
                <span className="relative h-6">
                  <span className="absolute inset-y-0 left-1/2 w-px bg-border-strong" aria-hidden="true" />
                  <span className={`anim-fill absolute top-1/2 h-3 -translate-y-1/2 ${towardLeft ? "rounded-l-sm" : "rounded-r-sm"} ${fav === toward ? "bg-accent/85" : "bg-underdog-strong"}`}
                        style={towardLeft ? { right: "50%", width, transformOrigin: "right" } : { left: "50%", width }} aria-hidden="true" />
                  <span className="fig absolute top-1/2 -translate-y-1/2 text-[11px] text-text/80" style={towardLeft ? { right: `calc(50% + ${width} + 6px)` } : { left: `calc(50% + ${width} + 6px)` }} aria-hidden="true">
                    {Math.abs(c.log_odds).toFixed(2)}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="min-h-[64px] rounded-lg border border-border bg-bg px-4 py-3 text-[12px]" aria-live="polite">
        {current ? (
          <>
            <p className="text-text">{featureLabel(current.feature)} <span className="fig text-muted">· {Math.abs(current.log_odds).toFixed(3)} log-odds toward {current.log_odds > 0 ? left : right}</span></p>
            <p className="mt-0.5 text-dim">{FEATURES[current.feature]?.help}</p>
            {INPUT_OF[current.feature] && (() => {
              const { key, fmt } = INPUT_OF[current.feature]!;
              const a = v.inputs[0][key], b = v.inputs[1][key];
              return a !== null && a !== undefined && b !== null && b !== undefined
                ? <p className="fig mt-1 text-muted">{left} {fmt(a)} · {right} {fmt(b)}</p> : null;
            })()}
          </>
        ) : (
          <p className="text-dim">Hover or focus a bar for its exact value and the inputs behind it.</p>
        )}
      </div>

      <p className="text-[12px] text-muted">
        The bars add up to log-odds of <span className="fig text-text">{v.log_odds.toFixed(3)}</span> for {left}, which is{" "}
        <span className="fig text-text">{left} {pct(v.p[0])}%</span> and <span className="fig text-text">{right} {pct(v.p[1])}%</span>.
        {quiet.length > 0 && <> No effect here: {quiet.map((c) => featureLabel(c.feature).toLowerCase()).join(", ")}.</>}
      </p>
      <p className="text-[11px] text-dim">
        Log-odds are the model&apos;s own units; near 50%, 0.1 is about 2.5 percentage points. Inputs overlap (overall and
        surface Elo especially), so one bar is not that input&apos;s independent effect, and none of this is a cause.
      </p>
    </div>
  );
}

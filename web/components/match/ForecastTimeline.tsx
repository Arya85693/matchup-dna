"use client";

import { useState } from "react";
import type { MatchPage } from "@/lib/contract";
import { familyName, favourite, pct } from "@/lib/format";
import { LocalTime } from "../LocalTime";
import { Badge } from "../ui";
import { MODEL, type Kind } from "./ForecastSummary";

const KINDS: Kind[] = ["tournament_start", "round_aware"];
const COLOR: Record<Kind, string> = { tournament_start: "var(--color-accent)", round_aware: "#c9ced6" };

/**
 * Every stored forecast version on a time axis, one lane per model, with the scheduled start and any result. Points
 * are discrete: nothing between them is implied, because the models are not updated continuously.
 */
export function ForecastTimeline({ page, names }: { page: MatchPage; names: readonly [string, string] }) {
  const [hover, setHover] = useState<string | null>(null);
  const versions = KINDS.flatMap((k) => page.versions[k].map((v) => ({ k, v })));
  if (versions.length === 0) {
    const last = page.decisions[page.decisions.length - 1];
    return <p className="text-[13px] text-muted">No forecast has been issued for this match.{last ? ` ${last.text}` : ""}</p>;
  }
  const lanes = KINDS.filter((k) => page.versions[k].length > 0 || k === "tournament_start");
  const start = page.match.start ? Date.parse(page.match.start) : null;
  const result = page.outcomes.length ? Math.min(...page.outcomes.map((o) => Date.parse(o.retrieved_at))) : null;
  const times = [...versions.map(({ v }) => Date.parse(v.issued_at)), ...(start ? [start] : []), ...(result ? [result] : [])];
  let lo = Math.min(...times), hi = Math.max(...times);
  if (hi - lo < 3_600_000) { lo -= 1_800_000; hi += 1_800_000; }
  const pad = (hi - lo) * 0.08;
  lo -= pad; hi += pad;
  const W = 1000, laneH = 40, top = 26, H = top + lanes.length * laneH + 34;
  const x = (t: number) => 130 + ((t - lo) / (hi - lo)) * (W - 160);
  // UTC so the server and the browser render identical text; the readout below the chart is in local time.
  const fmt = (t: number) => `${new Date(t).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} UTC`;
  const current = versions.find(({ v }) => v.prediction_id === hover);

  return (
    <div className="grid gap-3">
      {/* Phones: the same stored versions as a compact list (the chart's text would be too small to read). */}
      <ol className="grid gap-2 sm:hidden">
        {[...versions].sort((x, y) => x.v.issued_at.localeCompare(y.v.issued_at)).map(({ k, v }) => {
          const f = favourite(v.p) ?? 0;
          return (
            <li key={v.prediction_id} className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-[12px]">
              <span className="flex items-center gap-2">
                <span className="size-2.5 rounded-full border-2" style={{ borderColor: COLOR[k], background: v.counted ? COLOR[k] : "transparent" }} aria-hidden="true" />
                <span><span className="block text-text">{MODEL[k].label}</span><span className="fig text-dim"><LocalTime iso={v.issued_at} style="datetime" /></span></span>
              </span>
              <span className="fig text-right">{familyName(names[f])} {pct(v.p[f])}%<span className="block text-[11px] text-dim">{v.counted ? "Scored" : v.supersedes ? "Revision" : "Not counted"}</span></span>
            </li>
          );
        })}
      </ol>
      <svg viewBox={`0 0 ${W} ${H}`} className="hidden w-full sm:block" role="img" aria-label={`${versions.length} stored forecast versions between ${fmt(lo + pad)} and ${fmt(hi - pad)}`}>
        <line x1={130} x2={W - 20} y1={H - 26} y2={H - 26} stroke="var(--color-border-strong)" />
        {lanes.map((k, i) => (
          <g key={k}>
            <text x={0} y={top + i * laneH + laneH / 2 + 4} fontSize="13" fill="var(--color-muted)">{MODEL[k].label}</text>
            <line x1={130} x2={W - 20} y1={top + i * laneH + laneH / 2} y2={top + i * laneH + laneH / 2} stroke="var(--color-border)" strokeDasharray="2 4" />
          </g>
        ))}
        {start && (
          <g>
            <line x1={x(start)} x2={x(start)} y1={20} y2={H - 26} stroke="var(--color-muted)" strokeDasharray="4 4" />
            <text x={x(start)} y={14} textAnchor="middle" fontSize="12" fill="var(--color-muted)">Scheduled start</text>
          </g>
        )}
        {result && (
          <g>
            <line x1={x(result)} x2={x(result)} y1={20} y2={H - 26} stroke="var(--color-pos)" strokeOpacity="0.6" strokeDasharray="2 3" />
            <text x={x(result)} y={H - 8} textAnchor="middle" fontSize="12" fill="var(--color-pos)">Result recorded</text>
          </g>
        )}
        {versions.map(({ k, v }) => {
          const lane = lanes.indexOf(k);
          const cx = x(Date.parse(v.issued_at)), cy = top + lane * laneH + laneH / 2;
          const f = favourite(v.p) ?? 0;
          return (
            <g key={v.prediction_id} tabIndex={0} role="img" aria-label={`${MODEL[k].label} forecast issued ${fmt(Date.parse(v.issued_at))}: ${familyName(names[f])} ${pct(v.p[f])}%${v.counted ? ", scored" : ""}`}
               onMouseEnter={() => setHover(v.prediction_id)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(v.prediction_id)} onBlur={() => setHover(null)} className="cursor-default outline-none">
              <circle cx={cx} cy={cy} r={hover === v.prediction_id ? 8 : 6} fill={v.counted ? COLOR[k] : "var(--color-bg)"} stroke={COLOR[k]} strokeWidth="2" style={{ transition: "r 120ms" }} />
              <text x={cx + 13} y={cy + 4} fontSize="13" fill="var(--color-text)" fontFamily="var(--font-mono)">{familyName(names[f])} {pct(v.p[f])}%</text>
            </g>
          );
        })}
        <text x={130} y={H - 8} fontSize="12" fill="var(--color-dim)">{fmt(lo + pad)}</text>
      </svg>
      <div className="min-h-[40px] text-[12px]" aria-live="polite">
        {current ? (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-text">{MODEL[current.k].label}</span>
            <span className="fig text-muted"><LocalTime iso={current.v.issued_at} style="datetime" /></span>
            <span className="fig">{familyName(names[0])} {pct(current.v.p[0])}% · {familyName(names[1])} {pct(current.v.p[1])}%</span>
            {current.v.counted ? <Badge tone="accent">Scored</Badge> : <Badge>{current.v.supersedes ? "Revision, not scored" : "Not counted"}</Badge>}
          </p>
        ) : (
          <p className="text-dim">Filled points are the scored (first-issued) forecasts; hollow points are later revisions. Points are separate stored forecasts, not a continuous line.</p>
        )}
      </div>
    </div>
  );
}

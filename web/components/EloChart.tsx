"use client";

import { useMemo, useRef, useState } from "react";

export type Series = { name: string; points: [string, number][] };
const COLORS = ["var(--color-accent)", "#c9ced6"];   // teal and a light neutral: distinct in hue and lightness
const RANGES = [["6M", 182], ["1Y", 365], ["3Y", 1095]] as const;

/**
 * Elo over time (TradingView-style): range buttons, a crosshair that follows the pointer or keyboard, and a tooltip
 * with each series' rating at that date. Display only: these are the published ratings, not forecasts.
 */
export function EloChart({ series, height = 260 }: { series: Series[]; height?: number }) {
  const [range, setRange] = useState<(typeof RANGES)[number][0]>("1Y");
  const [hover, setHover] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const days = RANGES.find((r) => r[0] === range)![1];
  const W = 720, H = height, m = { l: 44, r: 12, t: 12, b: 26 };

  const data = useMemo(() => {
    const end = Math.max(...series.flatMap((s) => s.points.map(([d]) => Date.parse(d))));
    const start = end - days * 86_400_000;
    const shown = series.map((s) => ({ ...s, pts: s.points.map(([d, v]) => [Date.parse(d), v] as [number, number]).filter(([t]) => t >= start) }));
    const values = shown.flatMap((s) => s.pts.map(([, v]) => v));
    const lo = Math.floor((Math.min(...values) - 20) / 50) * 50, hi = Math.ceil((Math.max(...values) + 20) / 50) * 50;
    return { start, end, lo, hi, shown };
  }, [series, days]);

  const x = (t: number) => m.l + ((t - data.start) / Math.max(1, data.end - data.start)) * (W - m.l - m.r);
  const y = (v: number) => m.t + (1 - (v - data.lo) / Math.max(1, data.hi - data.lo)) * (H - m.t - m.b);
  const step = data.hi - data.lo > 400 ? 100 : 50;   // round gridlines: multiples of 50 or 100 Elo
  const ticks = Array.from({ length: Math.floor((data.hi - data.lo) / step) + 1 }, (_, i) => data.lo + i * step);
  const at = (pts: [number, number][], t: number) => {
    let last: [number, number] | undefined;
    for (const p of pts) { if (p[0] <= t) last = p; else break; }
    return last;
  };
  const move = (clientX: number) => {
    const box = svg.current?.getBoundingClientRect();
    if (!box) return;
    const px = ((clientX - box.left) / box.width) * W;
    const t = data.start + ((px - m.l) / (W - m.l - m.r)) * (data.end - data.start);
    setHover(Math.min(data.end, Math.max(data.start, t)));
  };
  const empty = data.shown.every((s) => s.pts.length < 2);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-4 text-[12px]">
          {series.map((s, i) => (
            <span key={s.name} className="inline-flex items-center gap-1.5 text-muted">
              <span className="h-0.5 w-4 rounded" style={{ background: COLORS[i] }} aria-hidden="true" />{s.name}
            </span>
          ))}
        </div>
        <div role="group" aria-label="Range" className="flex gap-1 rounded-md border border-border bg-bg p-0.5">
          {RANGES.map(([label]) => (
            <button key={label} aria-pressed={range === label} onClick={() => setRange(label)}
                    className={`rounded px-2.5 py-1 text-[12px] ${range === label ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>{label}</button>
          ))}
        </div>
      </div>
      {empty ? <p className="py-10 text-center text-muted">Not enough rated matches in this range.</p> : (
        <div className="relative">
          <svg ref={svg} viewBox={`0 0 ${W} ${H}`} className="w-full touch-none" role="img"
               aria-label={`Elo over the last ${range}: ${series.map((s) => `${s.name} ${Math.round(s.points.at(-1)?.[1] ?? 0)}`).join(", ")}`}
               tabIndex={0} onPointerMove={(e) => move(e.clientX)} onPointerLeave={() => setHover(null)}
               onKeyDown={(e) => {
                 const step = (data.end - data.start) / 40;
                 if (e.key === "ArrowLeft") setHover((h) => Math.max(data.start, (h ?? data.end) - step));
                 if (e.key === "ArrowRight") setHover((h) => Math.min(data.end, (h ?? data.start) + step));
               }}>
            {ticks.map((v) => (
              <g key={v}>
                <line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} stroke="var(--color-border)" />
                <text x={m.l - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--color-dim)">{Math.round(v)}</text>
              </g>
            ))}
            {[data.start, (data.start + data.end) / 2, data.end].map((t, i) => (
              <text key={i} x={x(t)} y={H - 6} textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"} fontSize="11" fill="var(--color-dim)">
                {new Date(t).toLocaleDateString("en-GB", { month: "short", year: "numeric" })}
              </text>
            ))}
            {data.shown.map((s, i) => s.pts.length > 1 && (
              <polyline key={`${s.name}-${range}`} className="anim-draw" pathLength={1} fill="none" stroke={COLORS[i]} strokeWidth="2" strokeLinejoin="round"
                        points={s.pts.map(([t, v]) => `${x(t).toFixed(1)},${y(v).toFixed(1)}`).join(" ")} />
            ))}
            {hover !== null && (
              <g>
                <line x1={x(hover)} x2={x(hover)} y1={m.t} y2={H - m.b} stroke="var(--color-border-strong)" />
                {data.shown.map((s, i) => { const p = at(s.pts, hover); return p && <circle key={s.name} cx={x(p[0])} cy={y(p[1])} r="4" fill={COLORS[i]} stroke="var(--color-card)" strokeWidth="2" />; })}
              </g>
            )}
          </svg>
          {hover !== null && (
            <div className="pointer-events-none absolute left-14 top-2 rounded-md border border-border-strong bg-bg px-3 py-2 text-[12px] shadow-lg">
              <p className="text-dim">{new Date(hover).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</p>
              {data.shown.map((s, i) => { const p = at(s.pts, hover); return <p key={s.name} className="num"><span style={{ color: COLORS[i] }}>●</span> {s.name} {p ? Math.round(p[1]) : "—"}</p>; })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * A small Elo trend for tables. With dated points it shows the date and rating under the pointer (or keyboard focus,
 * stepping with the arrow keys); the line is green when the trend ends higher than it starts, red when lower.
 */
export function Spark({ points, width = 84, height = 24 }: { points: [string, number][]; width?: number; height?: number }) {
  const [i, setI] = useState<number | null>(null);
  if (points.length < 2) return <span className="text-dim">—</span>;
  const values = points.map(([, v]) => v);
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const px = (k: number) => (k / (points.length - 1)) * width;
  const py = (v: number) => height - 3 - ((v - lo) / span) * (height - 6);
  const up = values[values.length - 1]! >= values[0]!;
  const fmt = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const first = points[0]!, last = points[points.length - 1]!;
  return (
    <span className="relative inline-block align-middle" onMouseLeave={() => setI(null)}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" tabIndex={0}
           aria-label={`Elo trend from ${Math.round(first[1])} on ${fmt(first[0])} to ${Math.round(last[1])} on ${fmt(last[0])}`}
           className="block cursor-crosshair rounded-sm outline-offset-2"
           onClick={(e) => e.stopPropagation()}
           onMouseMove={(e) => {
             const box = e.currentTarget.getBoundingClientRect();
             setI(Math.round(((e.clientX - box.left) / box.width) * (points.length - 1)));
           }}
           onFocus={() => setI(points.length - 1)} onBlur={() => setI(null)}
           onKeyDown={(e) => {
             if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); setI((k) => Math.max(0, (k ?? points.length - 1) - 1)); }
             if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); setI((k) => Math.min(points.length - 1, (k ?? 0) + 1)); }
           }}>
        <polyline className="anim-draw" pathLength={1} points={points.map(([, v], k) => `${px(k)},${py(v)}`).join(" ")} fill="none"
                  stroke={up ? "var(--color-pos)" : "var(--color-neg)"} strokeWidth="1.5" strokeLinejoin="round" />
        {i !== null && <circle cx={px(i)} cy={py(points[i]![1])} r="2.5" fill="var(--color-text)" />}
      </svg>
      {i !== null && (
        <span role="tooltip" className="pointer-events-none absolute bottom-full right-0 z-20 mb-1.5 whitespace-nowrap rounded border border-border-strong bg-bg px-2 py-1 text-[11px] shadow-lg">
          <span className="text-dim">{fmt(points[i]![0])}</span> <span className="fig text-text">{Math.round(points[i]![1])}</span>
        </span>
      )}
    </span>
  );
}

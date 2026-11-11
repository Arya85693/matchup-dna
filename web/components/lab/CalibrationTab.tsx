"use client";

import { useMemo, useState } from "react";
import type { Itf, TrackRecord } from "@/lib/contract";
import type { HISTORICAL as H } from "@/lib/research";
import { EvidenceTag, Finding, pc, SectionHead, type Evidence } from "./parts";

type Bin = { low: number; high: number; n: number; mean_p: number; observed: number; observed_low?: number; observed_high?: number };
type Dataset = { key: string; label: string; window: string; n: number; evidence: Evidence; color: string; bins: Bin[] };

type ItfBins = { bin: string; matches: number; forecast: number; observed: number }[];
const fromItf = (bins: ItfBins): Bin[] => bins.map((b) => {
  const [l, u] = b.bin.split("-").map(Number);
  return { low: l ?? 0, high: u ?? 0, n: b.matches, mean_p: b.forecast, observed: b.observed };
});

export function CalibrationTab({ h, record, itf, itfRecord }: {
  h: typeof H; record: TrackRecord | null; itf?: Itf["research"]; itfRecord?: Itf["record"] | null;
}) {
  const datasets = useMemo<Dataset[]>(() => {
    const list: Dataset[] = [
      { key: "p4", label: "Phase 4 tournament-start model", window: "Held-out matches, Jun – Oct 2026 (corrected)", n: h.phase4.held_out_corrected.scores.n, evidence: "retrospective", color: "var(--color-accent)", bins: h.phase4.held_out_corrected.reliability },
      { key: "p3", label: "Phase 3 model", window: "Reserved matches, Jan 2024 – May 2026", n: h.phase3.model.n, evidence: "held-out", color: "#c9ced6", bins: h.phase3.reliability },
    ];
    const live = record?.tournament_start.all;
    const liveBins = (live as { reliability?: { bin: string; n: number; mean_p: number; observed: number }[] } | undefined)?.reliability ?? [];
    if (live && live.n >= 30) {
      list.push({ key: "live", label: "Live record", window: "Prospective P1, scored so far", n: live.n, evidence: "interim", color: "var(--color-warn)",
        bins: liveBins.map((b) => { const [l, u] = b.bin.split("-").map(Number); return { low: l ?? 0, high: u ?? 0, n: b.n, mean_p: b.mean_p, observed: b.observed }; }) });
    }
    const itfHeld = itf?.calibration?.held_out.M1;
    if (itfHeld) {
      list.push({ key: "itf", label: "ITF M1 (ITF Men and ITF Women)", window: `Held-out matches, ${itf?.held_out.period ?? "Jan – Jun 2026"}`,
        n: itfHeld.bins.reduce((s, b) => s + b.matches, 0), evidence: "held-out", color: "#8fb3ff", bins: fromItf(itfHeld.bins) });
    }
    const itfLive = itfRecord?.m1;
    if (itfLive && itfLive.matches >= 30) {
      list.push({ key: "itf-live", label: "ITF live record", window: "Prospective P2, scored so far", n: itfLive.matches,
        evidence: "interim", color: "#e0a3ff", bins: fromItf(itfLive.reliability) });
    }
    return list;
  }, [h, record, itf, itfRecord]);
  const [shown, setShown] = useState<string[]>(datasets.map((d) => d.key));
  const [focus, setFocus] = useState(datasets[0]!.key);
  const visible = datasets.filter((d) => shown.includes(d.key));
  const focused = datasets.find((d) => d.key === focus) ?? datasets[0]!;
  const toggle = (key: string) => setShown((s) => (s.includes(key) ? (s.length > 1 ? s.filter((k) => k !== key) : s) : [...s, key]));

  return (
    <div className="grid gap-12">
      <Finding kicker="Calibration" title="Forecasts of about 75% won about 75% of the time.">
        In the 70–80% band, the Phase 4 model&apos;s forecasts averaged {pc(h.phase4.held_out_corrected.reliability.find((b) => Math.round(b.low * 10) === 7)?.mean_p ?? 0)} and
        those players won {pc(h.phase4.held_out_corrected.reliability.find((b) => Math.round(b.low * 10) === 7)?.observed ?? 0)}.
        Each point groups forecasts in a 10-point band and plots how often those players actually won; on the dashed
        diagonal, forecasts came true exactly as often as they said. The reports note that ATP forecasts run slightly
        overconfident; recalibration was not pre-registered, so it is not applied.
      </Finding>

      <section className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
        <Reliability datasets={visible} />
        <aside className="grid content-start gap-3">
          <p className="text-[12px] text-muted">Datasets</p>
          {datasets.map((d) => {
            const on = shown.includes(d.key);
            return (
              <button key={d.key} onClick={() => toggle(d.key)} onMouseEnter={() => setFocus(d.key)} onFocus={() => setFocus(d.key)} aria-pressed={on}
                      className={`grid gap-1.5 rounded-lg border px-4 py-3 text-left transition-colors ${on ? "border-border-strong bg-card" : "border-border opacity-60 hover:opacity-100"}`}>
                <span className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-2 text-[13px] font-medium"><span className="size-2.5 rounded-full" style={{ background: d.color }} />{d.label}</span>
                  <span className="text-[11px] text-dim">{on ? "Shown" : "Hidden"}</span>
                </span>
                <span className="text-[12px] text-dim">{d.window}</span>
                <span className="flex items-center gap-2"><EvidenceTag kind={d.evidence} /><span className="fig text-[11px] text-muted">{d.n.toLocaleString("en-GB")} matches</span></span>
              </button>
            );
          })}
          <p className="mt-2 text-[12px] text-dim">Click to show or hide. Point size reflects the number of matches; vertical lines are 95% intervals; hollow points have fewer than 20 matches.</p>
        </aside>
      </section>

      <section className="grid gap-5 border-t border-border pt-10">
        <SectionHead title={`Matches per band: ${focused.label}`}>Most forecasts sit near the middle: few matches are near-certain. Hover a dataset on the right to switch.</SectionHead>
        <div className="grid grid-cols-10 items-end gap-1.5" style={{ height: 96 }}>
          {Array.from({ length: 10 }, (_, i) => {
            const b = focused.bins.find((x) => Math.round(x.low * 10) === i);
            const max = Math.max(...focused.bins.map((x) => x.n));
            return (
              <div key={i} className="flex h-full flex-col justify-end" title={b ? `${Math.round(b.low * 100)}–${Math.round(b.high * 100)}%: ${b.n.toLocaleString("en-GB")} matches` : "No matches"}>
                <span className="fig mb-1 text-center text-[10px] text-dim">{b ? b.n.toLocaleString("en-GB") : 0}</span>
                <span className="anim-fade block rounded-t-sm" style={{ height: `${b ? Math.max(2, (b.n / max) * 64) : 1}px`, background: focused.color, opacity: 0.85 }} />
              </div>
            );
          })}
        </div>
        <div className="grid grid-cols-10 gap-1.5 text-center text-[10px] text-dim">{Array.from({ length: 10 }, (_, i) => <span key={i} className="fig">{i * 10}–{i * 10 + 10}</span>)}</div>
        <details className="text-[13px]">
          <summary className="cursor-pointer text-muted hover:text-text">Show the data</summary>
          <div className="mt-3 overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label="Calibration data">
            <table className="w-full min-w-[520px]">
              <thead><tr className="border-b border-border bg-card text-left text-[11px] text-dim"><th className="px-4 py-2 font-normal">Band</th><th className="px-3 py-2 text-right font-normal">Matches</th><th className="px-3 py-2 text-right font-normal">Average forecast</th><th className="px-3 py-2 text-right font-normal">Won</th><th className="px-4 py-2 text-right font-normal">95% interval</th></tr></thead>
              <tbody className="divide-y divide-border">
                {focused.bins.map((b) => (
                  <tr key={b.low}><td className="fig px-4 py-2 text-[12px]">{Math.round(b.low * 100)}–{Math.round(b.high * 100)}%</td><td className="fig px-3 py-2 text-right text-[12px] text-muted">{b.n.toLocaleString("en-GB")}</td><td className="fig px-3 py-2 text-right text-[12px]">{pc(b.mean_p)}</td><td className="fig px-3 py-2 text-right text-[12px]">{pc(b.observed)}</td><td className="fig px-4 py-2 text-right text-[12px] text-muted">{b.observed_low !== undefined ? `${pc(b.observed_low)} – ${pc(b.observed_high!)}` : "—"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>
    </div>
  );
}

function Reliability({ datasets }: { datasets: Dataset[] }) {
  const [hover, setHover] = useState<{ d: Dataset; b: Bin } | null>(null);
  const S = 520, m = { l: 52, r: 16, t: 16, b: 48 };
  const pw = S - m.l - m.r, ph = S - m.t - m.b;
  const x = (v: number) => m.l + v * pw, y = (v: number) => m.t + (1 - v) * ph;
  const maxN = Math.max(1, ...datasets.flatMap((d) => d.bins.map((b) => b.n)));
  return (
    <figure className="relative m-0 max-w-[600px]">
      <svg viewBox={`0 0 ${S} ${S}`} className="w-full" role="img" aria-label="Reliability diagram: forecast probability against observed win rate">
        {[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1].map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={m.t} y2={m.t + ph} stroke="var(--color-border)" strokeOpacity={t % 0.5 === 0 ? 1 : 0.5} />
            <line x1={m.l} x2={m.l + pw} y1={y(t)} y2={y(t)} stroke="var(--color-border)" strokeOpacity={t % 0.5 === 0 ? 1 : 0.5} />
            {[0, 0.25, 0.5, 0.75, 1].includes(Math.round(t * 100) / 100) && (
              <>
                <text x={x(t)} y={S - m.b + 18} textAnchor="middle" fontSize="11" fill="var(--color-dim)" fontFamily="var(--font-mono)">{Math.round(t * 100)}%</text>
                <text x={m.l - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--color-dim)" fontFamily="var(--font-mono)">{Math.round(t * 100)}%</text>
              </>
            )}
          </g>
        ))}
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="var(--color-muted)" strokeDasharray="5 5" />
        <text x={x(0.6)} y={y(0.51)} fontSize="11" fill="var(--color-dim)" transform={`rotate(-45 ${x(0.6)} ${y(0.51)})`}>perfect calibration</text>
        {datasets.map((d) => (
          <g key={d.key}>
            <polyline className="anim-draw" pathLength={1} fill="none" stroke={d.color} strokeOpacity="0.55" strokeWidth="1.5" points={d.bins.map((b) => `${x(b.mean_p)},${y(b.observed)}`).join(" ")} />
            {d.bins.map((b) => {
              const r = 3.5 + 6 * Math.sqrt(b.n / maxN);
              const active = hover?.d.key === d.key && hover.b.low === b.low;
              return (
                <g key={b.low}>
                  {b.observed_low !== undefined && b.observed_high !== undefined && (
                    <line x1={x(b.mean_p)} x2={x(b.mean_p)} y1={y(b.observed_low)} y2={y(b.observed_high)} stroke={d.color} strokeOpacity="0.45" strokeWidth="2" />
                  )}
                  <circle cx={x(b.mean_p)} cy={y(b.observed)} r={active ? r + 2 : r} fill={b.n < 20 ? "var(--color-bg)" : d.color} stroke={b.n < 20 ? d.color : "var(--color-bg)"} strokeWidth="2" style={{ transition: "r 120ms ease" }} />
                  <circle cx={x(b.mean_p)} cy={y(b.observed)} r="13" fill="transparent" tabIndex={0} role="img"
                          aria-label={`${d.label}, ${Math.round(b.low * 100)} to ${Math.round(b.high * 100)} percent: ${b.n} matches, forecast ${pc(b.mean_p)}, won ${pc(b.observed)}`}
                          onMouseEnter={() => setHover({ d, b })} onMouseLeave={() => setHover(null)} onFocus={() => setHover({ d, b })} onBlur={() => setHover(null)} />
                </g>
              );
            })}
          </g>
        ))}
        <text x={m.l + pw / 2} y={S - 8} textAnchor="middle" fontSize="12" fill="var(--color-muted)">Forecast probability</text>
        <text x={14} y={m.t + ph / 2} textAnchor="middle" fontSize="12" fill="var(--color-muted)" transform={`rotate(-90 14 ${m.t + ph / 2})`}>Observed win rate</text>
      </svg>
      <div className="pointer-events-none absolute left-[13%] top-3 min-w-[200px] rounded-md border border-border-strong bg-bg/95 px-3 py-2.5 text-[12px] transition-opacity" style={{ opacity: hover ? 1 : 0 }} aria-live="polite">
        {hover && (
          <>
            <p className="flex items-center gap-2 font-medium"><span className="size-2 rounded-full" style={{ background: hover.d.color }} />{hover.d.label}</p>
            <p className="fig mt-1 text-muted">Band {Math.round(hover.b.low * 100)}–{Math.round(hover.b.high * 100)}% · {hover.b.n.toLocaleString("en-GB")} matches</p>
            <p className="fig text-muted">Forecast {pc(hover.b.mean_p)} → won {pc(hover.b.observed)}</p>
            {hover.b.observed_low !== undefined && <p className="fig text-dim">95%: {pc(hover.b.observed_low)} – {pc(hover.b.observed_high!)}</p>}
          </>
        )}
      </div>
    </figure>
  );
}

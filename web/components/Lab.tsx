"use client";

import { useState } from "react";
import type { Models, TrackRecord } from "@/lib/contract";
import { featureLabel } from "@/lib/features";
import { utcDate } from "@/lib/format";
import type { HISTORICAL as H, MARKET as M } from "@/lib/research";
import { Badge, Card, EmptyState, Metric } from "./ui";

type Bin = { low: number; high: number; n: number; mean_p: number; observed: number; observed_low?: number; observed_high?: number };
const f4 = (v: number) => v.toFixed(4);
const pc = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;
const TABS = ["Live record", "Benchmarks", "Calibration", "Market", "Models"] as const;

export function Lab({ record, historical, market, models }: {
  record: TrackRecord | null; historical: typeof H; market: typeof M; models: Models | null;
}) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Live record");
  return (
    <div className="grid gap-6">
      <div role="tablist" aria-label="Model Lab sections" className="flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={t === tab} onClick={() => setTab(t)}
                  className={`-mb-px border-b-2 px-3 py-2.5 text-[13px] transition-colors ${t === tab ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}>
            {t}
          </button>
        ))}
      </div>
      <div role="tabpanel" aria-label={tab}>
        {tab === "Live record" && <Live record={record} />}
        {tab === "Benchmarks" && <Benchmarks h={historical} />}
        {tab === "Calibration" && <CalibrationTab h={historical} record={record} />}
        {tab === "Market" && <Market m={market} />}
        {tab === "Models" && <ModelsTab models={models} />}
      </div>
    </div>
  );
}

function num(m: object, key: string): number | null {
  const v = (m as Record<string, unknown>)[key];
  return typeof v === "number" ? v : null;
}

function Live({ record }: { record: TrackRecord | null }) {
  if (!record) return <div className="card"><EmptyState title="The live record could not be loaded" /></div>;
  const c = record.counts;
  const sum = (o: Record<string, number>) => Object.values(o).reduce((a, b) => a + b, 0);
  const ts = record.tournament_start.all;
  return (
    <div className="grid gap-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Forecasts recorded" value={sum(c.issued)} />
        <Metric label="Counted under the rules" value={sum(c.counted)} />
        <Metric label="Scored" value={sum(c.scored)} />
        <Metric label="Log loss (tournament start)" value={ts.n ? f4(num(ts, "log_loss") ?? 0) : "—"} note={ts.n ? `${ts.n} matches` : "No scored matches yet"} />
      </div>
      <Card title="About this record" action={<Badge tone="warn">Interim</Badge>}>
        <p className="text-muted">
          Forecasts issued from {utcDate(record.protocol.issued_from)} are scored under rules frozen that day: the first
          forecast per match counts, at least 30 minutes before the start. The single final evaluation runs on or after{" "}
          {utcDate(record.protocol.final_evaluation_not_before)}. Figures here are interim and decide nothing.
        </p>
        {c.excluded.length > 0 && <p className="mt-3 text-[12px] text-dim">Not scored yet: {c.excluded.map((e) => `${e.reason} (${e.n})`).join("; ")}</p>}
      </Card>
      {ts.n > 0 && (
        <Card title="Scores so far" padded={false}>
          <table className="w-full text-[13px]">
            <thead><tr className="border-b border-border text-left text-[12px] text-dim"><th className="px-5 py-3 font-normal">Forecasts</th><th className="px-3 py-3 text-right font-normal">Matches</th><th className="px-3 py-3 text-right font-normal">Log loss</th><th className="px-5 py-3 text-right font-normal">Favourite won</th></tr></thead>
            <tbody className="divide-y divide-border">
              {([["Tournament start", ts], ["ATP", record.tournament_start.ATP], ["WTA", record.tournament_start.WTA], ["Surface Elo benchmark", record.tournament_start.surface_elo_benchmark], ["Round-aware", record.round_aware.all]] as const)
                .filter(([, m]) => m.n > 0).map(([label, m]) => (
                  <tr key={label}><td className="px-5 py-3">{label}</td><td className="num px-3 py-3 text-right">{m.n}</td><td className="num px-3 py-3 text-right">{f4(num(m, "log_loss") ?? 0)}</td><td className="num px-5 py-3 text-right">{pc(num(m, "accuracy") ?? 0)}</td></tr>
                ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function Benchmarks({ h }: { h: typeof H }) {
  const p4 = h.phase4;
  const rows: { name: string; window: string; n: number; result: string; tag: React.ReactNode }[] = [
    { name: "Phase 3 model vs calibrated surface Elo", window: "Jan 2024 – May 2026", n: h.phase3.model.n, result: `${f4(h.phase3.model.log_loss)} vs ${f4(h.phase3.benchmark.log_loss)}`, tag: <Badge tone="accent">Held-out</Badge> },
    { name: "Serve and return added (Phase 4)", window: "Jun – Oct 2026", n: p4.held_out_original.p3_gap.rows, result: `${f4(p4.held_out_original.p3_gap.gap)} (p = ${p4.held_out_original.p3_gap.p.toFixed(3)})`, tag: <Badge tone="accent">Pre-registered</Badge> },
    { name: "Same, after a data correction", window: "Jun – Oct 2026", n: p4.held_out_corrected.p3_gap.rows, result: `${f4(p4.held_out_corrected.p3_gap.gap)} (p = ${p4.held_out_corrected.p3_gap.p.toFixed(3)})`, tag: <Badge>Retrospective</Badge> },
    { name: "Round-aware vs tournament start", window: "Jun – Oct 2026", n: p4.round_aware_original.rows, result: f4(p4.round_aware_original.gap), tag: <Badge tone="accent">Pre-registered</Badge> },
  ];
  const gaps = [
    { label: "Serve and return", note: "Pre-registered", g: p4.held_out_original.p3_gap },
    { label: "Serve and return", note: "Corrected", g: p4.held_out_corrected.p3_gap },
    { label: "Round-aware", note: "Pre-registered", g: p4.round_aware_original },
    { label: "Round-aware", note: "Corrected", g: p4.round_aware_corrected },
  ];
  return (
    <div className="grid gap-6">
      <Card title="Historical evaluations" padded={false}>
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Historical evaluations">
          <table className="w-full min-w-[640px] text-[13px]">
            <thead><tr className="border-b border-border text-left text-[12px] text-dim"><th className="px-5 py-3 font-normal">Comparison</th><th className="px-3 py-3 text-right font-normal">Matches</th><th className="px-3 py-3 text-right font-normal">Log loss</th><th className="px-5 py-3 font-normal">Evidence</th></tr></thead>
            <tbody className="divide-y divide-border">
              {rows.map((r) => (
                <tr key={r.name}><td className="px-5 py-3"><p>{r.name}</p><p className="text-[12px] text-dim">{r.window}</p></td><td className="num px-3 py-3 text-right">{r.n.toLocaleString("en-GB")}</td><td className="num px-3 py-3 text-right">{r.result}</td><td className="px-5 py-3">{r.tag}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Phase 4 gains, with 95% intervals" action={<span className="text-[12px] text-dim">Negative is better</span>}>
        <Intervals rows={gaps.map((x) => ({ label: x.label, note: x.note, value: x.g.gap, low: x.g.low, high: x.g.high }))} />
        <p className="mt-4 text-[12px] text-dim">An interval crossing zero is not called an improvement. The pre-registered serve-and-return result (p = {p4.held_out_original.p3_gap.p.toFixed(3)}) is the official verdict.</p>
      </Card>
      <Card title="By year (post-hoc)" padded={false}>
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="By year">
          <table className="w-full min-w-[520px] text-[13px]">
            <thead><tr className="border-b border-border text-left text-[12px] text-dim"><th className="px-5 py-3 font-normal">Year</th><th className="px-3 py-3 text-right font-normal">Matches</th><th className="px-3 py-3 text-right font-normal">Model</th><th className="px-3 py-3 text-right font-normal">Elo</th><th className="px-5 py-3 text-right font-normal">Favourite won</th></tr></thead>
            <tbody className="divide-y divide-border">
              {h.phase4.long_run_by_year.map((y) => (
                <tr key={y.year}><td className="px-5 py-3">{y.year}{y.year <= 2023 && <span className="ml-2 text-[12px] text-dim">selection years</span>}</td><td className="num px-3 py-3 text-right text-muted">{y.phase4.n.toLocaleString("en-GB")}</td><td className="num px-3 py-3 text-right">{f4(y.phase4.log_loss)}</td><td className="num px-3 py-3 text-right text-muted">{f4(y.elo.log_loss)}</td><td className="num px-5 py-3 text-right">{pc(y.phase4.accuracy)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Intervals({ rows }: { rows: { label: string; note?: string; value: number; low: number | null; high: number | null }[] }) {
  const ext = rows.flatMap((r) => [r.value, r.low ?? r.value, r.high ?? r.value, 0]);
  const pad = (Math.max(...ext) - Math.min(...ext)) * 0.1 || 0.01;
  const lo = Math.min(...ext) - pad, hi = Math.max(...ext) + pad;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <ul className="grid gap-1">
      {rows.map((r, i) => (
        <li key={i} className="grid grid-cols-[150px_minmax(0,1fr)_72px] items-center gap-4 py-1.5" title={`${r.label}: ${f4(r.value)}${r.low !== null && r.high !== null ? ` (95%: ${f4(r.low)} to ${f4(r.high)})` : ""}`}>
          <div><p className="text-[13px]">{r.label}</p>{r.note && <p className="text-[11px] text-dim">{r.note}</p>}</div>
          <div className="relative h-6">
            <span className="absolute inset-y-0 w-px bg-border-strong" style={{ left: x(0) }} aria-hidden="true" />
            {r.low !== null && r.high !== null && <span className="absolute top-1/2 h-px -translate-y-1/2 bg-muted" style={{ left: x(r.low), width: `calc(${x(r.high)} - ${x(r.low)})` }} aria-hidden="true" />}
            <span className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent" style={{ left: x(r.value) }} aria-hidden="true" />
          </div>
          <span className="num text-right text-[13px]">{r.value > 0 ? "+" : ""}{f4(r.value)}</span>
        </li>
      ))}
    </ul>
  );
}

function CalibrationTab({ h, record }: { h: typeof H; record: TrackRecord | null }) {
  const live = (record?.tournament_start.all as { reliability?: { bin: string; n: number; mean_p: number; observed: number }[] } | undefined)?.reliability ?? [];
  const sets: { key: string; label: string; note: string; bins: Bin[] }[] = [
    { key: "p4", label: "Phase 4, held-out", note: `Jun–Oct 2026 · ${h.phase4.held_out_corrected.scores.n.toLocaleString("en-GB")} matches`, bins: h.phase4.held_out_corrected.reliability },
    { key: "p3", label: "Phase 3, reserved", note: `Jan 2024–May 2026 · ${h.phase3.model.n.toLocaleString("en-GB")} matches`, bins: h.phase3.reliability },
  ];
  if ((record?.tournament_start.all.n ?? 0) >= 30) {
    sets.unshift({ key: "live", label: "Live record (interim)", note: `${record!.tournament_start.all.n} matches`, bins: live.map((b) => { const [l, u] = b.bin.split("-").map(Number); return { low: l ?? 0, high: u ?? 0, n: b.n, mean_p: b.mean_p, observed: b.observed }; }) });
  }
  const [key, setKey] = useState(sets[0]!.key);
  const set = sets.find((s) => s.key === key) ?? sets[0]!;
  return (
    <Card title="Calibration" action={
      <div role="group" aria-label="Dataset" className="flex gap-1 rounded-md border border-border bg-bg p-0.5">
        {sets.map((s) => <button key={s.key} aria-pressed={s.key === key} onClick={() => setKey(s.key)} className={`rounded px-2.5 py-1 text-[12px] ${s.key === key ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>{s.label}</button>)}
      </div>
    }>
      <div className="grid gap-8 md:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
        <ReliabilityChart bins={set.bins} />
        <div className="grid content-start gap-3 text-muted">
          <p className="text-text">{set.label}</p>
          <p className="text-[12px] text-dim">{set.note}</p>
          <p>Each point groups forecasts in a 10-point band. Points on the diagonal came true exactly as often as forecast. Hover a point for its numbers.</p>
        </div>
      </div>
    </Card>
  );
}

function ReliabilityChart({ bins }: { bins: Bin[] }) {
  const [hover, setHover] = useState<Bin | null>(null);
  const W = 420, H = 380, m = { l: 44, r: 12, t: 12, b: 40 };
  const pw = W - m.l - m.r, ph = H - m.t - m.b;
  const x = (v: number) => m.l + v * pw, y = (v: number) => m.t + (1 - v) * ph;
  const maxN = Math.max(...bins.map((b) => b.n), 1);
  return (
    <figure className="relative m-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Calibration: forecast probability against observed win rate">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={m.t} y2={m.t + ph} stroke="var(--color-border)" />
            <line x1={m.l} x2={m.l + pw} y1={y(t)} y2={y(t)} stroke="var(--color-border)" />
            <text x={x(t)} y={H - m.b + 18} textAnchor="middle" fontSize="11" fill="var(--color-dim)">{Math.round(t * 100)}%</text>
            <text x={m.l - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--color-dim)">{Math.round(t * 100)}%</text>
          </g>
        ))}
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="var(--color-muted)" strokeDasharray="4 4" />
        <polyline fill="none" stroke="var(--color-accent)" strokeWidth="1.5" strokeOpacity=".5" points={bins.map((b) => `${x(b.mean_p)},${y(b.observed)}`).join(" ")} />
        {bins.map((b) => (
          <g key={b.low}>
            {b.observed_low !== undefined && b.observed_high !== undefined && <line x1={x(b.mean_p)} x2={x(b.mean_p)} y1={y(b.observed_low)} y2={y(b.observed_high)} stroke="var(--color-accent)" strokeOpacity=".4" strokeWidth="2" />}
            <circle cx={x(b.mean_p)} cy={y(b.observed)} r={3 + 5 * Math.sqrt(b.n / maxN)} fill={hover === b ? "var(--color-text)" : "var(--color-accent)"} stroke="var(--color-card)" strokeWidth="2" />
            <circle cx={x(b.mean_p)} cy={y(b.observed)} r="14" fill="transparent" tabIndex={0} aria-label={`${Math.round(b.low * 100)} to ${Math.round(b.high * 100)} percent: ${b.n} matches, forecast ${pc(b.mean_p)}, won ${pc(b.observed)}`}
                    onMouseEnter={() => setHover(b)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(b)} onBlur={() => setHover(null)} />
          </g>
        ))}
        <text x={m.l + pw / 2} y={H - 4} textAnchor="middle" fontSize="11" fill="var(--color-muted)">Forecast probability</text>
      </svg>
      {hover && (
        <div className="pointer-events-none absolute right-2 top-2 rounded-md border border-border-strong bg-bg px-3 py-2 text-[12px] shadow-lg">
          <p className="font-medium">{Math.round(hover.low * 100)}–{Math.round(hover.high * 100)}% forecasts</p>
          <p className="num text-muted">{hover.n.toLocaleString("en-GB")} matches</p>
          <p className="num text-muted">Forecast {pc(hover.mean_p)} · Won {pc(hover.observed)}</p>
        </div>
      )}
    </figure>
  );
}

function Market({ m }: { m: typeof M }) {
  const q1 = m.gaps["Phase 4"]!;
  const primary = m.backtests["primary"]!;
  const slices = [
    ...Object.entries(m.by_year).map(([k, g]) => ({ label: k, g })),
    ...Object.entries(m.by_tour).map(([k, g]) => ({ label: k, g })),
    { label: "Top-20 player involved", g: m.by_ranking["better-ranked player top 20"]! },
    { label: "Both outside top 100", g: m.by_ranking["outside 100"]! },
  ].filter((s) => s.g);
  return (
    <div className="grid gap-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Market log loss" value={f4(m.scores["opening market"]!.log_loss)} note="Opening prices, margin removed" />
        <Metric label="Model log loss" value={f4(m.scores["Phase 4"]!.log_loss)} note={`${m.matches.toLocaleString("en-GB")} matches`} />
        <Metric label="Market advantage" value={`+${f4(q1.gap)}`} note={`95%: +${f4(q1.low ?? 0)} to +${f4(q1.high ?? 0)}`} tone="neg" />
        <Metric label="Paper betting return" value={pc(primary.roi)} note={`${primary.bets.toLocaleString("en-GB")} bets, no real money`} tone="neg" />
      </div>
      <Card title="Model minus market, by slice" action={<span className="text-[12px] text-dim">Positive = market better</span>}>
        <Intervals rows={slices.map((s) => ({ label: s.label, note: `${s.g.matches.toLocaleString("en-GB")} matches`, value: s.g.gap, low: s.g.low, high: s.g.high }))} />
      </Card>
      <Card title="What it means">
        <p className="text-muted">The betting market forecast better in every slice. Blending the model into the price added nothing, and a paper betting rule lost money. Matchup DNA makes no betting recommendations. Prices: Valuebetennis (CC BY 4.0); they carry no timestamps.</p>
      </Card>
    </div>
  );
}

function ModelsTab({ models }: { models: Models | null }) {
  if (!models) return <div className="card"><EmptyState title="Models could not be loaded" /></div>;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {models.models.map((m) => (
        <Card key={m.model_version} title={m.kind === "tournament_start" ? "Tournament start" : "Round-aware update"} action={<span className="mono text-dim">{m.model_version}</span>}>
          <div className="grid gap-4 text-[13px]">
            <div><p className="label">Uses</p><ul className="mt-1.5 grid gap-1 text-muted">{m.uses.map((u) => <li key={u}>{u}</li>)}</ul></div>
            <div><p className="label">Does not use</p><ul className="mt-1.5 grid gap-1 text-muted">{m.does_not_use.map((u) => <li key={u}>{u}</li>)}</ul></div>
            <div><p className="label">Inputs</p><p className="mt-1.5 text-muted">{[...new Set(Object.values(m.features).flat())].map(featureLabel).join(", ")}</p></div>
            <div><p className="label">Fingerprint (SHA-256)</p><p className="mono mt-1.5 break-all text-dim">{m.artifact_sha256}</p></div>
          </div>
        </Card>
      ))}
    </div>
  );
}

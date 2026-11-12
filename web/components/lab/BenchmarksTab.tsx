"use client";

import { useState } from "react";
import type { HISTORICAL as H, MARKET as M } from "@/lib/research";
import { EVIDENCE, EvidenceTag, f4, Finding, pc, SectionHead, Segmented, sgn4, type Evidence } from "./parts";

const NEUTRAL = "var(--color-neutral)";

export function BenchmarksTab({ h, m }: { h: typeof H; m: typeof M }) {
  const p4 = h.phase4;
  return (
    <div className="grid gap-12">
      <Finding kicker="Model evolution" evidence="frozen"
        title="Each generation lowered log loss, by small steps. The market sits below them all."
        aside={<Evolution m={m} />}>
        Scored on the same {m.matches.toLocaleString("en-GB")} matches ({m.window}), the ratings-only models trail the
        machine-learning models, and the Phase 4 model is the best of Matchup DNA&apos;s. Among the Phase 4 additions, only the round-aware gain passed its
        pre-registered test with an interval that excludes zero; the serve-and-return gain did not.
      </Finding>

      <section className="grid gap-6">
        <SectionHead title="Evidence ledger">Every comparison, with how strong its evidence is. Gaps are the newer model minus the older one; negative is better.</SectionHead>
        <div className="overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label="Evidence ledger">
          <table className="w-full min-w-[820px] text-[13px]">
            <thead>
              <tr className="border-b border-border bg-card text-left text-[11px] text-dim">
                <th className="px-4 py-2.5 font-normal">Comparison</th><th className="px-3 py-2.5 font-normal">Evidence</th>
                <th className="px-3 py-2.5 text-right font-normal">Matches</th><th className="px-3 py-2.5 font-normal">Result</th>
                <th className="w-[230px] px-4 py-2.5 font-normal">Gap and 95% interval</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <Row name="Surface Elo vs Elo (Phase 2)" window={h.phase2.window} kind="development" n={h.phase2.ATP.n + h.phase2.WTA.n}
                   result={`ATP ${h.phase2.ATP.surface_elo} vs ${h.phase2.ATP.elo}; WTA ${h.phase2.WTA.surface_elo} vs ${h.phase2.WTA.elo}`} />
              <Row name="Machine-learning model vs calibrated surface Elo (Phase 3)" window="Jan 2024 – May 2026, reserved and scored once" kind="held-out" n={h.phase3.model.n}
                   result={`${f4(h.phase3.model.log_loss)} vs ${f4(h.phase3.benchmark.log_loss)}; favourite won ${pc(h.phase3.model.accuracy)}`} />
              <Row name="Serve and return added (Phase 4)" window="Jun – Oct 2026. Official verdict: not a statistically supported improvement" kind="pre-registered" n={p4.held_out_original.p3_gap.rows}
                   result={`p = ${p4.held_out_original.p3_gap.p.toFixed(3)}`} gap={p4.held_out_original.p3_gap} />
              <Row name="Same, after a data correction (erratum 1)" window="65 matches had been counted twice; supporting evidence only" kind="retrospective" n={p4.held_out_corrected.p3_gap.rows}
                   result={`p = ${p4.held_out_corrected.p3_gap.p.toFixed(3)}`} gap={p4.held_out_corrected.p3_gap} />
              <Row name="Round-aware update vs tournament start" window="Later-round matches, Jun – Oct 2026" kind="pre-registered" n={p4.round_aware_original.rows}
                   result={`p = ${p4.round_aware_original.p.toFixed(3)}`} gap={p4.round_aware_original} />
              <Row name="Round-aware, after the correction" window="Supporting evidence only" kind="retrospective" n={p4.round_aware_corrected.rows}
                   result={`p = ${p4.round_aware_corrected.p.toFixed(3)}`} gap={p4.round_aware_corrected} />
            </tbody>
          </table>
        </div>
        <dl className="grid gap-x-8 gap-y-2 text-[12px] sm:grid-cols-2 lg:grid-cols-3">
          {(["pre-registered", "held-out", "frozen", "retrospective", "development", "post-hoc"] as Evidence[]).map((k) => (
            <div key={k} className="flex items-start gap-2.5"><dt className="shrink-0"><EvidenceTag kind={k} /></dt><dd className="text-dim">{EVIDENCE[k].meaning}</dd></div>
          ))}
        </dl>
      </section>

      <section className="grid gap-6 border-t border-border pt-10">
        <YearByYear h={h} />
      </section>
    </div>
  );
}

/** Log loss of each model on the identical Phase 5 matches, with the market drawn as the reference line. */
function Evolution({ m }: { m: typeof M }) {
  const steps: [string, string][] = [["Elo", "Elo"], ["Surface Elo", "Surface Elo"], ["Phase 3", "Phase 3 model"], ["Phase 4", "Phase 4 model"]];
  const market = m.scores["opening market"]!.log_loss;
  const values = steps.map(([k]) => m.scores[k]!.log_loss);
  const lo = Math.floor((market - 0.004) * 200) / 200, hi = Math.ceil((Math.max(...values) + 0.002) * 200) / 200;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <figure className="m-0">
      <div className="grid grid-cols-[104px_minmax(0,1fr)_56px] gap-x-3 gap-y-3">
        {steps.map(([k, label], i) => {
          const v = m.scores[k]!.log_loss;
          return (
            <div key={k} className="contents" title={`${label}: ${f4(v)}`}>
              <span className="self-center text-[12px] text-muted">{label}</span>
              <div className="relative h-6">
                {i === 0 && <span className="pointer-events-none absolute top-0 z-10 w-px border-l border-dashed border-muted" style={{ left: x(market), height: "calc(4 * 1.5rem + 3 * 0.75rem)" }} aria-hidden="true" />}
                <span className="anim-fill absolute left-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-track" style={{ width: x(v), animationDelay: `${i * 90}ms` }} aria-hidden="true" />
                <span className={`absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg ${k === "Phase 4" ? "bg-accent" : "bg-muted"}`} style={{ left: x(v) }} aria-hidden="true" />
              </div>
              <span className="fig self-center text-right text-[12px]">{f4(v)}</span>
            </div>
          );
        })}
        <span />
        <div className="relative h-5"><span className="fig absolute top-0 -translate-x-1/2 whitespace-nowrap text-[11px] text-muted" style={{ left: x(market) }}>Market {f4(market)}</span></div>
        <span />
      </div>
      <figcaption className="mt-2 text-[11px] text-dim">Log loss, lower is better (axis {lo.toFixed(3)} to {hi.toFixed(3)}). Dashed line: the opening betting market. Same matches for every model.</figcaption>
    </figure>
  );
}

function Row({ name, window, kind, n, result, gap }: {
  name: string; window: string; kind: Evidence; n: number; result: string;
  gap?: { gap: number; low: number; high: number };
}) {
  return (
    <tr className="align-top transition-colors hover:bg-card">
      <td className="px-4 py-3"><p>{name}</p><p className="mt-0.5 text-[11px] text-dim">{window}</p></td>
      <td className="px-3 py-3"><EvidenceTag kind={kind} /></td>
      <td className="fig px-3 py-3 text-right text-[12px] text-muted">{n.toLocaleString("en-GB")}</td>
      <td className="fig px-3 py-3 text-[12px]">{result}</td>
      <td className="px-4 py-3">{gap ? <MiniInterval {...gap} /> : <span className="text-[11px] text-dim">Scores shown in the result</span>}</td>
    </tr>
  );
}

/** One gap with its interval on a shared −0.012 … +0.002 scale, so rows are comparable. */
function MiniInterval({ gap, low, high }: { gap: number; low: number; high: number }) {
  const lo = -0.012, hi = 0.002;
  const x = (v: number) => `${((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * 100}%`;
  const excludesZero = high < 0 || low > 0;
  return (
    <div title={`${sgn4(gap)} (95%: ${sgn4(low)} to ${sgn4(high)})`}>
      <div className="relative h-4">
        <span className="absolute inset-y-0 w-px bg-border-strong" style={{ left: x(0) }} aria-hidden="true" />
        <span className={`absolute top-1/2 h-0.5 -translate-y-1/2 ${excludesZero ? "bg-accent/60" : "bg-muted/60"}`} style={{ left: x(low), width: `calc(${x(high)} - ${x(low)})` }} aria-hidden="true" />
        <span className={`absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ${excludesZero ? "bg-accent" : "bg-muted"}`} style={{ left: x(gap) }} aria-hidden="true" />
      </div>
      <p className="fig mt-1 text-[11px] text-muted">{sgn4(gap)} <span className="text-dim">[{sgn4(low)}, {sgn4(high)}]</span></p>
    </div>
  );
}

function YearByYear({ h }: { h: typeof H }) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const years = h.phase4.long_run_by_year;
  const all = years.flatMap((y) => [y.phase4.log_loss, y.elo.log_loss]);
  const lo = Math.floor(Math.min(...all) * 100) / 100 - 0.005, hi = Math.ceil(Math.max(...all) * 100) / 100 + 0.005;
  const W = 640, Hh = 220, m = { l: 48, r: 16, t: 14, b: 30 };
  const x = (i: number) => m.l + (i + 0.5) * ((W - m.l - m.r) / years.length);
  const y = (v: number) => m.t + ((v - lo) / (hi - lo)) * (Hh - m.t - m.b);   // lower log loss drawn higher
  const ticks = [lo + 0.005, (lo + hi) / 2, hi - 0.005];
  const selection = years.filter((yr) => yr.year <= 2023).length;
  return (
    <>
      <SectionHead title="Year by year" action={<Segmented label="View" value={view} onChange={setView} options={[["chart", "Chart"], ["table", "Table"]]} />}>
        The Phase 4 model&apos;s chronological predictions against Elo. <EvidenceTag kind="post-hoc" /> The shaded years were used to choose the model, so they flatter it.
      </SectionHead>
      {view === "chart" ? (
        <figure className="m-0 max-w-[760px]">
          <svg viewBox={`0 0 ${W} ${Hh}`} className="w-full" role="img" aria-label="Log loss by year: Phase 4 model and Elo">
            <rect x={m.l} y={m.t} width={(W - m.l - m.r) * (selection / years.length)} height={Hh - m.t - m.b} fill="var(--color-card)" />
            {ticks.map((t) => (
              <g key={t}><line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} stroke="var(--color-border)" /><text x={m.l - 8} y={y(t) + 4} textAnchor="end" fontSize="10" fill="var(--color-dim)" fontFamily="var(--font-mono)">{t.toFixed(3)}</text></g>
            ))}
            {[["elo", NEUTRAL], ["phase4", "var(--color-accent)"]].map(([key, color]) => (
              <g key={key}>
                <polyline className="anim-draw" pathLength={1} fill="none" stroke={color} strokeWidth="2" points={years.map((yr, i) => `${x(i)},${y(yr[key as "elo" | "phase4"].log_loss)}`).join(" ")} />
                {years.map((yr, i) => <circle key={yr.year} cx={x(i)} cy={y(yr[key as "elo" | "phase4"].log_loss)} r="4" fill={color} stroke="var(--color-bg)" strokeWidth="2"><title>{`${yr.year} ${key === "elo" ? "Elo" : "Phase 4"}: ${f4(yr[key as "elo" | "phase4"].log_loss)} (${yr.phase4.n.toLocaleString("en-GB")} matches)`}</title></circle>)}
              </g>
            ))}
            {years.map((yr, i) => <text key={yr.year} x={x(i)} y={Hh - 8} textAnchor="middle" fontSize="11" fill="var(--color-muted)" fontFamily="var(--font-mono)">{yr.year}</text>)}
          </svg>
          <figcaption className="mt-2 flex flex-wrap gap-4 text-[12px] text-muted">
            <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-accent" />Phase 4 model</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-4 rounded" style={{ background: NEUTRAL }} />Elo</span>
            <span className="text-dim">Lower is better; higher on the chart is better. 2026 runs to October.</span>
          </figcaption>
        </figure>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label="Year by year">
          <table className="w-full min-w-[520px] text-[13px]">
            <thead><tr className="border-b border-border bg-card text-left text-[11px] text-dim"><th className="px-4 py-2.5 font-normal">Year</th><th className="px-3 py-2.5 text-right font-normal">Matches</th><th className="px-3 py-2.5 text-right font-normal">Phase 4</th><th className="px-3 py-2.5 text-right font-normal">Elo</th><th className="px-4 py-2.5 text-right font-normal">Favourite won</th></tr></thead>
            <tbody className="divide-y divide-border">
              {years.map((yr) => (
                <tr key={yr.year}><td className="px-4 py-2.5">{yr.year}{yr.year <= 2023 && <span className="ml-2 text-[11px] text-dim">selection years</span>}</td><td className="fig px-3 py-2.5 text-right text-[12px] text-muted">{yr.phase4.n.toLocaleString("en-GB")}</td><td className="fig px-3 py-2.5 text-right text-[12px]">{f4(yr.phase4.log_loss)}</td><td className="fig px-3 py-2.5 text-right text-[12px] text-muted">{f4(yr.elo.log_loss)}</td><td className="fig px-4 py-2.5 text-right text-[12px]">{pc(yr.phase4.accuracy)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

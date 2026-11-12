"use client";

import type { MARKET as M } from "@/lib/research";
import { f4, Finding, FigureStrip, pc, SectionHead, sgn4 } from "./parts";

const MARKET_COLOR = "var(--color-neutral)";
const RANK_LABELS: Record<string, string> = {
  "better-ranked player top 20": "Top-20 player involved",
  "21-100": "Better-ranked player 21–100",
  "outside 100": "Both outside the top 100",
};

export function MarketTab({ m }: { m: typeof M }) {
  const q1 = m.gaps["Phase 4"]!;
  const market = m.scores["opening market"]!, model = m.scores["Phase 4"]!;
  const primary = m.backtests["primary"]!;
  const kelly = Object.entries(m.backtests).find(([k]) => k.includes("Kelly"))?.[1];
  const blend = m.gaps["blend Phase 4"];
  const unranked = m.by_ranking["a rank missing"];

  return (
    <div className="grid gap-12">
      <Finding kicker="Against the betting market" evidence="frozen"
        title="The betting market forecast better than Matchup DNA."
        aside={
          <div className="grid gap-2">
            <p className="text-[12px] text-muted">Model log loss minus market log loss, per match</p>
            <p className="fig text-[44px] font-medium leading-none text-neg">{sgn4(q1.gap)}</p>
            <p className="fig text-[12px] text-dim">95% interval {sgn4(q1.low ?? 0)} to {sgn4(q1.high ?? 0)} · {m.matches.toLocaleString("en-GB")} matches · {m.window}</p>
          </div>
        }>
        Opening prices from bookmakers, with their margin removed, were compared with the Phase 4 model on the same matches
        under rules frozen in advance. The market was more accurate on every measure and in every slice tested.
      </Finding>

      <section className="grid gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div className="grid content-start gap-5">
          <SectionHead title="Head to head">Same {m.matches.toLocaleString("en-GB")} matches. Each metric on its own scale.</SectionHead>
          <div className="mb-1 flex gap-4 text-[12px] text-muted">
            <span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-sm" style={{ background: MARKET_COLOR }} />Opening market</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-sm bg-accent" />Matchup DNA, Phase 4</span>
          </div>
          {([["Log loss", "lower is better", market.log_loss, model.log_loss, f4], ["Brier score", "lower is better", market.brier, model.brier, f4], ["Favourite won", "higher is better", market.accuracy, model.accuracy, (v: number) => pc(v, 2)]] as const).map(([label, note, a, b, fmt]) => {
            const pad = Math.abs(a - b) * 0.6;
            const lo = Math.min(a, b) - pad, hi = Math.max(a, b) + pad;
            const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
            return (
              <div key={label} className="grid gap-2 rounded-md px-2 py-2 transition-colors hover:bg-card">
                <p className="flex justify-between text-[12px]"><span>{label}</span><span className="text-dim">{note}</span></p>
                <div className="relative h-8">
                  <span className="absolute inset-x-0 top-1/2 h-px bg-border-strong" aria-hidden="true" />
                  <span className="anim-fill absolute top-1/2 h-0.5 -translate-y-1/2 bg-neg/60" style={{ left: x(Math.min(a, b)), width: `calc(${x(Math.max(a, b))} - ${x(Math.min(a, b))})` }} aria-hidden="true" />
                  {[["Market", a, MARKET_COLOR], ["Phase 4", b, "var(--color-accent)"]].map(([who, v, color]) => (
                    <span key={who as string} className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg" style={{ left: x(v as number), background: color as string }} title={`${who}: ${fmt(v as number)}`} />
                  ))}
                </div>
                <p className="fig flex justify-between text-[11px] text-dim"><span>{fmt(lo)}</span><span className="text-muted">Market {fmt(a)} · Phase 4 {fmt(b)}</span><span>{fmt(hi)}</span></p>
              </div>
            );
          })}
          <p className="text-[11px] text-dim">Each row is zoomed to its own range (end labels show it), so read the figures for size.</p>
        </div>

        <div className="grid content-start gap-5">
          <SectionHead title="The gap by year">Positive means the market was better. Lines are 95% intervals.</SectionHead>
          <YearColumns years={Object.entries(m.by_year)} />
        </div>
      </section>

      <section className="grid gap-5 border-t border-border pt-10">
        <SectionHead title="Where the gap is">Model minus market log loss by slice. Every slice favours the market.</SectionHead>
        <ul className="grid gap-1">
          {[...Object.entries(m.by_tour).map(([k, g]) => [k, g] as const), ...Object.entries(m.by_ranking).filter(([k]) => RANK_LABELS[k]).map(([k, g]) => [RANK_LABELS[k]!, g] as const)].map(([label, g]) => (
            <SliceRow key={label} label={label} n={g.matches} gap={g.gap} low={g.low} high={g.high} />
          ))}
        </ul>
        {unranked && <p className="text-[12px] text-dim">Not drawn, to keep the scale readable: matches with an unranked player ({unranked.matches} matches), where the market was better by {f4(unranked.gap)}. Slices are descriptive: with this many, about one would look notable by chance.</p>}
      </section>

      <section className="grid gap-6 border-t border-border pt-10">
        <div className="rounded-lg border border-neg/30 bg-neg/[0.04] px-6 py-5">
          <p className="text-[15px] font-medium">The model did not demonstrate a profitable market edge.</p>
          <p className="mt-1.5 text-[13px] text-muted">Every check pointed the same way. Matchup DNA makes no betting recommendations.</p>
        </div>
        <FigureStrip items={[
          { label: "Paper betting return", value: pc(primary.roi), tone: "neg", note: `${primary.bets.toLocaleString("en-GB")} bets${primary.roi_interval ? `, 95% ${pc(primary.roi_interval[0])} to ${pc(primary.roi_interval[1])}` : ""}` },
          { label: "Cost of the margin alone", value: primary.expected_roi_if_market_right !== null ? pc(primary.expected_roi_if_market_right) : "—", note: "If the market were exactly right; the model did worse" },
          { label: "Blending into the price", value: blend && Math.abs(blend.gap) >= 0.00005 ? sgn4(blend.gap) : "0.0000", note: "Log loss gained: nothing measurable" },
          { label: "Information slope", value: m.information_slope.b.toFixed(3), note: `95% ${m.information_slope.low.toFixed(3)} to ${m.information_slope.high.toFixed(3)}; no added information` },
          ...(kelly ? [{ label: "Quarter Kelly", value: pc(kelly.roi), tone: "neg" as const, note: "Bankroll wiped out" }] : []),
        ]} />
        <p className="text-[12px] text-dim">
          Paper test only; no real money. Closing prices were better still than opening prices, by {f4(Math.abs(m.closing["closing minus opening"]?.gap ?? 0))} log loss.
          Historical prices carry no timestamps; betting limits and liquidity were not modelled. Prices: Valuebetennis (CC BY 4.0).
        </p>
      </section>
    </div>
  );
}

function YearColumns({ years }: { years: [string, { matches: number; gap: number; low: number | null; high: number | null }][] }) {
  const max = Math.max(...years.map(([, g]) => g.high ?? g.gap)) * 1.25;
  const H = 180;
  const y = (v: number) => H - (v / max) * H;
  return (
    <div className="relative flex items-end justify-around gap-4 border-b border-border-strong" style={{ height: H + 24 }}>
      {years.map(([year, g], i) => (
        <div key={year} className="relative flex h-full w-16 flex-col items-center justify-end" title={`${year}: ${sgn4(g.gap)} (95% ${sgn4(g.low ?? g.gap)} to ${sgn4(g.high ?? g.gap)}), ${g.matches.toLocaleString("en-GB")} matches`}>
          <span className="fig absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-[11px]" style={{ bottom: `${H - y(g.high ?? g.gap) + 6}px` }}>{sgn4(g.gap)}</span>
          <span className="anim-fade w-full rounded-t-sm bg-neg/70" style={{ height: `${H - y(g.gap)}px`, animationDelay: `${i * 90}ms` }} />
          {g.low !== null && g.high !== null && (
            <span className="absolute left-1/2 w-0.5 -translate-x-1/2 bg-text/70" style={{ bottom: `${H - y(g.low)}px`, height: `${y(g.low) - y(g.high)}px` }} aria-hidden="true" />
          )}
          <span className="fig absolute -bottom-6 text-[11px] text-muted">{year}</span>
        </div>
      ))}
    </div>
  );
}

function SliceRow({ label, n, gap, low, high }: { label: string; n: number; gap: number; low: number | null; high: number | null }) {
  const lo = 0, hi = 0.07;
  const x = (v: number) => `${(Math.min(hi, Math.max(lo, v)) / hi) * 100}%`;
  return (
    <li className="grid grid-cols-[minmax(0,180px)_minmax(0,1fr)_72px] items-center gap-4 rounded-md px-2 py-2 transition-colors hover:bg-card sm:grid-cols-[220px_minmax(0,1fr)_80px]"
        title={`${label}: ${sgn4(gap)}${low !== null && high !== null ? ` (95% ${sgn4(low)} to ${sgn4(high)})` : ""}`}>
      <div><p className="text-[13px]">{label}</p><p className="fig text-[11px] text-dim">{n.toLocaleString("en-GB")} matches</p></div>
      <div className="relative h-5">
        <span className="absolute inset-y-0 left-0 w-px bg-border-strong" aria-hidden="true" />
        {low !== null && high !== null && <span className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-neg/40" style={{ left: x(low), width: `calc(${x(high)} - ${x(low)})` }} aria-hidden="true" />}
        <span className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-neg" style={{ left: x(gap) }} aria-hidden="true" />
      </div>
      <span className="fig text-right text-[12px]">{sgn4(gap)}</span>
    </li>
  );
}

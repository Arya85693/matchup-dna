"use client";

import Link from "next/link";
import { useState } from "react";
import type { HistoryListing, MatchSummary } from "@/lib/contract";
import { favourite, pct, roundLabel } from "@/lib/format";
import { Spark } from "./EloChart";
import { LocalTime } from "./LocalTime";
import { Badge, ProbBar, SurfaceDot } from "./ui";

/** Flip through upcoming forecasts; each card switches between the two models. A model without a forecast shows its
 * stored reason and no number (the other model's number is never borrowed). */
export function FeaturedCarousel({ matches }: { matches: MatchSummary[] }) {
  const [i, setI] = useState(0);
  const [kind, setKind] = useState<"tournament_start" | "round_aware">("tournament_start");
  if (matches.length === 0) return null;
  const m = matches[i % matches.length]!;
  const f = m.forecasts[kind];
  const fav = f.available ? favourite(f.p) : null;
  const go = (d: number) => { setI((v) => (v + d + matches.length) % matches.length); setKind("tournament_start"); };
  return (
    <div className="card lift relative overflow-hidden p-6 hover:border-border-strong">
      <div className="flex items-center justify-between gap-3 text-[12px] text-muted">
        <span className="inline-flex items-center gap-2"><SurfaceDot surface={m.edition.surface} />{m.edition.name} · {roundLabel(m.round)}</span>
        <span className="num">{m.start && <LocalTime iso={m.start} style="datetime" />}</span>
      </div>
      <div key={`${m.uid}-${kind}`} className="anim-fade mt-6 grid gap-4">
        {m.players.map((p, k) => (
          <div key={k} className="flex items-baseline justify-between gap-4">
            <span className={`truncate text-[22px] ${fav === k ? "font-semibold" : "text-text/75"}`}>{p.name}</span>
            {f.available && <span className={`num text-[28px] ${fav === k ? "font-semibold text-accent" : "text-muted"}`}>{pct(f.p[k as 0 | 1])}%</span>}
          </div>
        ))}
        {f.available ? <ProbBar p={f.p} height={8} /> : <p className="rounded-md border border-dashed border-border-strong px-3 py-2.5 text-[12px] text-muted">{f.reason}</p>}
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Model" className="flex gap-1 rounded-md border border-border bg-bg p-0.5">
          {(["tournament_start", "round_aware"] as const).map((k) => (
            <button key={k} aria-pressed={kind === k} onClick={() => setKind(k)}
                    className={`rounded px-2.5 py-1 text-[12px] ${kind === k ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>
              {k === "tournament_start" ? "Before the event" : "After earlier rounds"}
            </button>
          ))}
        </div>
        <Link href={`/matches/${m.uid}`} className="link text-[13px]">Why? See the reasoning</Link>
      </div>
      <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
        <span className="num text-[12px] text-dim">{(i % matches.length) + 1} of {matches.length} upcoming forecasts</span>
        <div className="flex gap-2">
          <button onClick={() => go(-1)} aria-label="Previous match" className="rounded-md border border-border px-3 py-1.5 text-[13px] text-muted hover:bg-card-hover hover:text-text">←</button>
          <button onClick={() => go(1)} aria-label="Next match" className="rounded-md border border-border px-3 py-1.5 text-[13px] text-muted hover:bg-card-hover hover:text-text">→</button>
        </div>
      </div>
    </div>
  );
}

const STEPS = [
  { title: "Rate every player", short: "Elo from 360,000 matches" },
  { title: "Add the context", short: "Ranking, rest, form, serve" },
  { title: "Make the forecast", short: "One probability per match" },
  { title: "Lock it and score it", short: "Recorded before play" },
];

/** A four-step walkthrough. Step one has a live Elo playground (an illustration of the formula, not a forecast). */
export function HowItWorks() {
  const [step, setStep] = useState(0);
  const [a, setA] = useState(2050);
  const [b, setB] = useState(1900);
  const expected = 1 / (1 + 10 ** ((b - a) / 400));
  return (
    <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
      <ol className="grid content-start gap-1">
        {STEPS.map((s, k) => (
          <li key={s.title}>
            <button onClick={() => setStep(k)} aria-pressed={step === k}
                    className={`flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${step === k ? "bg-card text-text" : "text-muted hover:bg-card/60 hover:text-text"}`}>
              <span className={`num mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] ${step === k ? "bg-accent text-bg" : "border border-border-strong"}`}>{k + 1}</span>
              <span><span className="block text-[13px] font-medium">{s.title}</span><span className="block text-[12px] text-dim">{s.short}</span></span>
            </button>
          </li>
        ))}
      </ol>
      <div className="card min-h-[260px] p-6" aria-live="polite">
        {step === 0 && (
          <div className="grid gap-5">
            <p className="text-muted">Every result moves two ratings: the winner gains, the loser drops, and upsets move them more. The gap between two ratings gives each player&apos;s chance. Drag the sliders.</p>
            {([["Player A", "elo-a", a, setA], ["Player B", "elo-b", b, setB]] as const).map(([label, id, value, set]) => (
              <label key={label} className="grid gap-2">
                <span className="flex justify-between text-[13px]"><span>{label}</span><span className="num text-muted">{value} Elo</span></span>
                <input id={id} type="range" min={1400} max={2400} step={10} value={value} onChange={(e) => set(Number(e.target.value))} className="accent-[var(--color-accent)]" />
              </label>
            ))}
            <div>
              <div className="flex justify-between text-[13px]"><span>A wins <span className="num font-semibold">{(expected * 100).toFixed(0)}%</span></span><span>B wins <span className="num font-semibold">{((1 - expected) * 100).toFixed(0)}%</span></span></div>
              <div className="mt-2"><ProbBar p={[expected, 1 - expected]} height={8} /></div>
              <p className="mt-2 text-[12px] text-dim">Illustration of the Elo formula only. Real forecasts use more than Elo.</p>
            </div>
          </div>
        )}
        {step === 1 && (
          <div className="grid gap-4">
            <p className="text-muted">Elo is only the start. The model also looks at what Elo misses:</p>
            <ul className="grid gap-3 sm:grid-cols-2">
              {[["Surface", "A separate rating on hard, clay and grass"], ["Ranking", "The official ranking before the match"], ["Rest", "How long since each player last played"], ["Form", "Recent results against Elo's expectations"], ["Serve and return", "Points won, adjusted for the opponents faced"], ["This week", "For later rounds: how each player has played so far"]].map(([t, d]) => (
                <li key={t} className="rounded-lg border border-border px-4 py-3"><p className="text-[13px] font-medium">{t}</p><p className="mt-0.5 text-[12px] text-dim">{d}</p></li>
              ))}
            </ul>
          </div>
        )}
        {step === 2 && (
          <div className="grid gap-4">
            <p className="text-muted">A statistical model weighs those inputs and turns them into one number: each player&apos;s chance of winning. Every match page shows which inputs pushed the forecast which way.</p>
            <div className="grid gap-2">
              {[["Serve", 0.62], ["Ranking", 0.38], ["Surface Elo", 0.3], ["Recent form", -0.18], ["Rest", -0.1]].map(([label, v]) => (
                <div key={label as string} className="grid grid-cols-[110px_1fr] items-center gap-3 text-[12px] text-muted">
                  <span>{label}</span>
                  <div className="relative h-3"><span className="absolute inset-y-0 left-1/2 w-px bg-border-strong" /><span className="absolute top-0.5 h-2 rounded-sm bg-accent/80" style={(v as number) > 0 ? { left: "50%", width: `${(v as number) * 45}%` } : { right: "50%", width: `${-(v as number) * 45}%` }} /></div>
                </div>
              ))}
            </div>
            <p className="text-[12px] text-dim">Shape of the chart on every match page (example values).</p>
          </div>
        )}
        {step === 3 && (
          <div className="grid gap-4">
            <p className="text-muted">Each forecast is stored at least 30 minutes before the first serve and can never be edited. Every entry is chained to the one before, so the record can be checked. After the match, it is scored, including the misses.</p>
            <div className="flex flex-wrap items-center gap-2 text-[12px]">
              {["Forecast issued", "Locked in the ledger", "Match played", "Scored in public"].map((t, k) => (
                <span key={t} className="flex items-center gap-2"><Badge tone={k === 1 ? "accent" : "neutral"}>{t}</Badge>{k < 3 && <span className="text-dim">→</span>}</span>
              ))}
            </div>
            <div className="flex flex-wrap gap-4 text-[13px]"><Link href="/archive" className="link">See the forecast archive</Link><Link href="/lab" className="link">See how it scores</Link></div>
          </div>
        )}
      </div>
    </div>
  );
}

/** The top of the Elo table, switchable by tour. */
export function TopPlayers({ players }: { players: HistoryListing[] }) {
  const [tour, setTour] = useState<"ATP" | "WTA">("ATP");
  const top = players.filter((p) => p.tour === tour).sort((x, y) => x.elo_rank - y.elo_rank).slice(0, 8);
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <h3 className="text-[13px] font-medium">Top rated right now</h3>
        <div role="group" aria-label="Tour" className="flex gap-1 rounded-md border border-border bg-bg p-0.5">
          {(["ATP", "WTA"] as const).map((t) => (
            <button key={t} aria-pressed={tour === t} onClick={() => setTour(t)} className={`rounded px-2.5 py-1 text-[12px] ${tour === t ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>{t}</button>
          ))}
        </div>
      </div>
      <ul className="divide-y divide-border">
        {top.map((p) => (
          <li key={p.id}>
            <Link href={`/players/${p.id}`} className="grid grid-cols-[24px_minmax(0,1fr)_auto_72px] items-center gap-3 px-5 py-2.5 hover:bg-card-hover">
              <span className="num text-[12px] text-dim">{p.elo_rank}</span>
              <span className="truncate">{p.name}</span>
              <span className="num text-[13px] font-medium">{Math.round(p.elo)}</span>
              <Spark values={p.spark} />
            </Link>
          </li>
        ))}
      </ul>
      <Link href="/players" className="block border-t border-border px-5 py-3 text-[13px] text-muted hover:bg-card-hover hover:text-text">
        All {players.filter((p) => p.tour === tour).length} {tour} players →
      </Link>
    </div>
  );
}


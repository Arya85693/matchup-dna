"use client";

import Link from "next/link";
import type { MatchPage } from "@/lib/contract";
import { familyName, favourite, pct, roundLabel, STATE_LABELS } from "@/lib/format";
import { LocalTime } from "../LocalTime";
import { Badge, SurfaceDot } from "../ui";
import { ProbabilitySplit, Pct, TierBadge } from "./parts";

export type Kind = "tournament_start" | "round_aware";
export const MODEL: Record<Kind, { label: string; short: string; about: string }> = {
  tournament_start: { label: "Tournament start", short: "Before the event", about: "Uses only information from before the tournament began." },
  round_aware: { label: "Round-aware", short: "After earlier rounds", about: "Adds this tournament's completed earlier rounds to the same information." },
};

/** The centrepiece: both players, the selected model's stored probabilities, and how the two models differ. */
export function ForecastSummary({ page, kind, onKind }: { page: MatchPage; kind: Kind; onKind: (k: Kind) => void }) {
  const m = page.match;
  const f = m.forecasts[kind];
  const ts = m.forecasts.tournament_start, ra = m.forecasts.round_aware;
  const fav = f.available ? favourite(f.p) : null;
  const winner = m.result?.winner_index ?? null;
  const names = [m.players[0].name ?? "To be decided", m.players[1].name ?? "To be decided"] as const;

  return (
    <section aria-label="Forecast" className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border px-5 py-3 text-[12px] text-muted sm:px-6">
        <SurfaceDot surface={m.edition.surface} withLabel />
        <TierBadge tour={m.tour} level={m.edition.level} />
        <span>{roundLabel(m.round)}</span>
        {m.best_of && <span>Best of {m.best_of}</span>}
        <span className="fig">{m.start ? <LocalTime iso={m.start} style="datetime" /> : "Start time to be confirmed"}</span>
        {m.state !== "scheduled" && m.state !== "time_tbc" && <Badge tone={m.state === "completed" ? "neutral" : "warn"}>{STATE_LABELS[m.state]}</Badge>}
      </div>

      <div className="grid gap-7 px-5 py-7 sm:px-8 sm:py-9">
        {/* Model switch */}
        <div role="tablist" aria-label="Model" className="grid grid-cols-2 gap-1 rounded-lg border border-border bg-bg p-1 sm:max-w-[520px]">
          {(["tournament_start", "round_aware"] as const).map((k) => {
            const ff = m.forecasts[k];
            return (
              <button key={k} role="tab" aria-selected={kind === k} onClick={() => onKind(k)}
                      className={`grid gap-0.5 rounded-md px-3 py-2 text-left transition-colors ${kind === k ? "bg-card-hover" : "hover:bg-card"}`}>
                <span className={`text-[13px] ${kind === k ? "font-medium text-text" : "text-muted"}`}>{MODEL[k].label}</span>
                <span className="text-[11px] text-dim">{ff.available ? <>{MODEL[k].short} · issued <LocalTime iso={ff.issued_at} /></> : "Not issued for this match"}</span>
              </button>
            );
          })}
        </div>

        {/* Players and probabilities */}
        <div className="grid gap-4">
          <div className="grid grid-cols-2 items-end gap-6">
            {names.map((n, i) => (
              <div key={i} className={`grid gap-2 ${i === 1 ? "justify-items-end text-right" : ""}`}>
                <div>
                  <p className={`text-[19px] leading-tight sm:text-[24px] ${fav === i || winner === i ? "font-semibold text-text" : "text-text/80"}`}>{n}</p>
                  <p className="mt-1 flex flex-wrap gap-x-2 text-[12px] text-dim">
                    {m.players[i]!.seed !== null && <span>Seed {m.players[i]!.seed}</span>}
                    {m.players[i]!.identity === "new_player" && <span>New to the records</span>}
                    {winner === i && <span className="text-pos">Won</span>}
                    {fav === i && <span className="text-accent">Favourite</span>}
                  </p>
                </div>
                {f.available ? <Pct value={f.p[i as 0 | 1]} fav={fav === i} size="xl" /> : <span className="fig text-[40px] leading-none text-border-strong sm:text-[48px]" aria-hidden="true">–</span>}
              </div>
            ))}
          </div>
          {f.available ? <ProbabilitySplit p={f.p} height={12} /> : (
            <div className="rounded-lg border border-dashed border-border-strong px-4 py-3 text-[13px] text-muted">
              <span className="text-text">No {MODEL[kind].label.toLowerCase()} forecast.</span> {f.reason}
            </div>
          )}
          {m.result?.score && <p className="fig text-[13px] text-muted">Final score {m.result.score}</p>}
        </div>

        {/* Change between the two stored forecasts */}
        {ts.available && ra.available && (
          <div className="grid gap-1 rounded-lg border border-border bg-bg px-4 py-3 text-[13px] sm:flex sm:items-center sm:gap-4">
            <span className="text-muted">Tournament start → round-aware</span>
            {[0, 1].map((i) => {
              const d = (ra.p[i as 0 | 1] - ts.p[i as 0 | 1]) * 100;
              return (
                <span key={i} className="fig">
                  {familyName(names[i as 0 | 1])} {pct(ts.p[i as 0 | 1])}% → <span className="text-text">{pct(ra.p[i as 0 | 1])}%</span>
                  <span className={`ml-1.5 ${d > 0 ? "text-pos" : d < 0 ? "text-neg" : "text-dim"}`}>({d > 0 ? "+" : d < 0 ? "−" : ""}{Math.abs(d).toFixed(1)} pts)</span>
                </span>
              );
            })}
            <span className="text-[11px] text-dim sm:ml-auto">Two separate stored forecasts, not a continuous update</span>
          </div>
        )}

        {/* Provenance of the shown forecast */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-4 text-[12px] text-muted">
          <span>{MODEL[kind].about}</span>
          {f.available && (
            <>
              <span className="mono text-dim">{f.model_version}</span>
              <span>Issued <span className="fig"><LocalTime iso={f.issued_at} style="datetime" /></span></span>
              {f.counted ? <Badge tone="accent">Scored forecast</Badge> : <Badge>Not counted</Badge>}
              {f.revision && <span className="fig">Revised to {pct(f.revision.p[0])}% / {pct(f.revision.p[1])}% at <LocalTime iso={f.revision.issued_at} style="datetime" /> (not scored)</span>}
            </>
          )}
          <Link href="/methodology" className="link ml-auto">How the models differ</Link>
        </div>
      </div>
    </section>
  );
}

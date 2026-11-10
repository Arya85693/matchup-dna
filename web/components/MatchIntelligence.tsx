"use client";

import Link from "next/link";
import { useState } from "react";
import type { MatchPage, Version } from "@/lib/contract";
import { notRecorded } from "@/lib/format";
import { ContributionChart } from "./match/ContributionChart";
import { ForecastSummary, MODEL, type Kind } from "./match/ForecastSummary";
import { ForecastTimeline } from "./match/ForecastTimeline";
import { PlayerComparison } from "./match/PlayerComparison";
import { Verification } from "./match/Verification";

/** The counted version of a model's forecast if there is one, else its first stored version. */
const headline = (versions: Version[]) => versions.find((v) => v.counted) ?? versions[0];

function Panel({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border px-5 py-3.5">
        <h2 className="text-[13px] font-medium">{title}</h2>
        {aside && <span className="text-[12px] text-dim">{aside}</span>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

export function MatchIntelligence({ page }: { page: MatchPage }) {
  const m = page.match;
  const [kind, setKind] = useState<Kind>("tournament_start");
  const names = [m.players[0].name ?? "To be decided", m.players[1].name ?? "To be decided"] as const;
  const version = headline(page.versions[kind]);
  const fallback = headline(page.versions.tournament_start);
  // A match with no recorded forecast from either model: nothing to analyse, so only the players, the score and the
  // verification records are shown (owner's decision, 10 November 2026).
  const nothing = !m.forecasts.tournament_start.available && !m.forecasts.round_aware.available
    && notRecorded(m.forecasts.tournament_start.reason_code);

  if (nothing) {
    return (
      <div className="grid gap-6 [&>*]:min-w-0">
        <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[13px] text-muted">
          <Link href="/matches" className="hover:text-text">Matches</Link><span className="text-dim">/</span>
          <span className="truncate text-text">{m.edition.name}</span>
        </nav>
        <ForecastSummary page={page} kind={kind} onKind={setKind} />
        <Verification page={page} />
      </div>
    );
  }

  return (
    <div className="grid gap-6 [&>*]:min-w-0">
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[13px] text-muted">
        <Link href="/matches" className="hover:text-text">Matches</Link><span className="text-dim">/</span>
        <span className="truncate text-text">{m.edition.name}</span>
      </nav>

      <ForecastSummary page={page} kind={kind} onKind={setKind} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <Panel title="Why the model leans this way" aside={MODEL[kind].label}>
          {version ? <ContributionChart key={`${kind}-${version.prediction_id}`} v={version} names={names} />
            : <p className="text-[13px] text-muted">No {MODEL[kind].label.toLowerCase()} forecast for this match, so there is nothing to explain.</p>}
        </Panel>
        <Panel title="Player comparison" aside={version ? "As the model saw them" : fallback ? "Inputs from the tournament-start forecast" : undefined}>
          {(version ?? fallback) ? <PlayerComparison v={(version ?? fallback)!} names={names} roundAware={kind === "round_aware" && Boolean(version)} />
            : <p className="text-[13px] text-muted">Shown once a forecast exists.</p>}
        </Panel>
      </div>

      <Panel title="Forecast history" aside="Every stored version">
        <ForecastTimeline page={page} names={names} />
      </Panel>

      <Verification page={page} />
    </div>
  );
}

"use client";

import Link from "next/link";
import { useState } from "react";
import type { Forecast, MatchPage, Version } from "@/lib/contract";
import { FEATURES, featureLabel } from "@/lib/features";
import { familyName, favourite, levelLabel, pct, roundLabel, STATE_LABELS } from "@/lib/format";
import { LocalTime } from "./LocalTime";
import { Badge, Card, ProbBar, SurfaceDot } from "./ui";

type Kind = "tournament_start" | "round_aware";
const MODEL: Record<Kind, { label: string; short: string; about: string }> = {
  tournament_start: { label: "Tournament start", short: "Before the tournament", about: "Uses only information from before the tournament began." },
  round_aware: { label: "Round-aware", short: "After earlier rounds", about: "Adds this tournament's completed earlier rounds to the same information." },
};

const headline = (versions: Version[]) => versions.find((v) => v.counted) ?? versions[0];

export function MatchIntelligence({ page }: { page: MatchPage }) {
  const m = page.match;
  const [kind, setKind] = useState<Kind>("tournament_start");
  const forecast: Forecast = m.forecasts[kind];
  const version = headline(page.versions[kind]);
  const names = [m.players[0].name ?? "", m.players[1].name ?? ""] as const;
  const fav = forecast.available ? favourite(forecast.p) : null;

  return (
    <div className="grid gap-6">
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[13px] text-muted">
        <Link href="/matches" className="hover:text-text">Matches</Link><span className="text-dim">/</span><span className="text-text">{m.edition.name}</span>
      </nav>

      {/* Header: players and the selected model's forecast */}
      <section className="card p-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted">
          <SurfaceDot surface={m.edition.surface} withLabel />
          <span>{levelLabel(m.tour, m.edition.level)}</span>
          <span>{roundLabel(m.round)}</span>
          {m.best_of && <span>Best of {m.best_of}</span>}
          <span className="num">{m.start ? <LocalTime iso={m.start} style="datetime" /> : "Start time to be confirmed"}</span>
          {m.state !== "scheduled" && m.state !== "time_tbc" && <Badge tone={m.state === "completed" ? "neutral" : "warn"}>{STATE_LABELS[m.state]}</Badge>}
        </div>

        <div className="mt-6 grid gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,320px)] md:items-center">
          <div className="grid gap-3">
            {m.players.map((p, i) => (
              <div key={i} className="flex items-baseline justify-between gap-4">
                <div className="min-w-0">
                  <span className={`text-[20px] ${fav === i ? "font-semibold" : "text-text/85"}`}>{p.name ?? "To be decided"}</span>
                  {m.result?.winner_index === i && <Badge tone="pos">Won</Badge>}
                  <p className="num text-[12px] text-dim">
                    {p.rank !== null ? `Rank ${p.rank}` : "Unranked"}{p.seed !== null ? ` · Seed ${p.seed}` : ""}
                    {p.identity === "new_player" ? " · New to the records" : ""}
                  </p>
                </div>
                {forecast.available && <span className={`num text-[20px] ${fav === i ? "font-semibold text-text" : "text-muted"}`}>{pct(forecast.p[i as 0 | 1])}%</span>}
              </div>
            ))}
            {forecast.available && <ProbBar p={forecast.p} height={6} />}
            {m.result?.score && <p className="num text-[13px] text-muted">Final score {m.result.score}</p>}
          </div>

          <div className="grid gap-3 md:border-l md:border-border md:pl-8">
            <div role="tablist" aria-label="Model" className="grid grid-cols-2 gap-1 rounded-lg border border-border bg-bg p-1">
              {(["tournament_start", "round_aware"] as const).map((k) => (
                <button key={k} role="tab" aria-selected={k === kind} onClick={() => setKind(k)}
                        className={`rounded-md px-2 py-1.5 text-[12px] transition-colors ${k === kind ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>
                  {MODEL[k].label}{!m.forecasts[k].available && <span className="ml-1 text-dim">—</span>}
                </button>
              ))}
            </div>
            <p className="text-[12px] text-muted">{MODEL[kind].about}</p>
            {forecast.available ? (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12px]">
                <dt className="text-dim">Issued</dt><dd className="num"><LocalTime iso={forecast.issued_at} style="datetime" /></dd>
                <dt className="text-dim">Version</dt><dd className="mono">{forecast.model_version}</dd>
                <dt className="text-dim">Status</dt>
                <dd>{forecast.counted ? <Badge tone="accent">Scored forecast</Badge> : <Badge>Not counted</Badge>}</dd>
                {forecast.revision && (
                  <><dt className="text-dim">Revised</dt><dd className="num">{pct(forecast.revision.p[0])}% / {pct(forecast.revision.p[1])}% (not scored)</dd></>
                )}
              </dl>
            ) : (
              <p className="rounded-md border border-dashed border-border-strong px-3 py-2.5 text-[12px] text-muted">{forecast.reason}</p>
            )}
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Why the model leans this way" action={<span className="text-[12px] text-dim">{MODEL[kind].short}</span>}>
          {version ? <Contributions v={version} names={names} /> : <p className="text-muted">No {MODEL[kind].label.toLowerCase()} forecast for this match.</p>}
        </Card>
        <Card title="Player comparison" action={<span className="text-[12px] text-dim">As the model saw them</span>}>
          {version ? <Comparison v={version} names={names} roundAware={kind === "round_aware"} /> : <p className="text-muted">Shown once a forecast exists.</p>}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card title="Forecast history" padded={false}>
          <History page={page} names={names} />
        </Card>
        <Card title="Verification">
          {version ? (
            <dl className="grid gap-y-2 text-[12px] sm:grid-cols-[120px_minmax(0,1fr)]">
              <dt className="text-dim">Prediction</dt><dd className="mono break-all">{version.prediction_id}</dd>
              <dt className="text-dim">Model</dt><dd className="mono break-all">{version.integrity.model_sha256}</dd>
              <dt className="text-dim">Code</dt><dd className="mono break-all">{version.integrity.code_sha256} {version.integrity.code_matches_protocol && <Badge tone="accent">Matches frozen protocol</Badge>}</dd>
              <dt className="text-dim">Ledger</dt><dd className="mono">#{version.integrity.ledger_position} · {version.integrity.record_hash.slice(0, 16)}</dd>
            </dl>
          ) : <p className="text-muted">No forecast to verify.</p>}
          <p className="mt-4 text-[12px] text-dim">Stored forecasts cannot be edited; each is hash-chained into the public <Link href="/archive" className="link">forecast archive</Link>.</p>
        </Card>
      </div>
    </div>
  );
}

function Contributions({ v, names }: { v: Version; names: readonly [string, string] }) {
  const active = v.contributions.filter((c) => Math.abs(c.log_odds) >= 0.0005);
  const scale = Math.max(0.2, ...active.map((c) => Math.abs(c.log_odds)));
  return (
    <div>
      <div className="mb-3 grid grid-cols-[132px_1fr] text-[12px] text-dim">
        <span />
        <div className="flex justify-between"><span>{familyName(names[0])}</span><span>{familyName(names[1])}</span></div>
      </div>
      <ul className="grid gap-2">
        {active.map((c) => {
          const w = `${(Math.abs(c.log_odds) / scale) * 46}%`;
          const left = c.log_odds > 0;
          return (
            <li key={c.feature} className="grid grid-cols-[132px_1fr] items-center gap-x-3" title={`${FEATURES[c.feature]?.help ?? ""} ${c.log_odds > 0 ? "+" : ""}${c.log_odds.toFixed(3)} log-odds`}>
              <span className="truncate text-[12px] text-muted">{featureLabel(c.feature)}</span>
              <div className="relative h-5">
                <span className="absolute inset-y-0 left-1/2 w-px bg-border-strong" aria-hidden="true" />
                <span className="absolute top-1/2 h-2 -translate-y-1/2 rounded-sm bg-accent/80" style={left ? { right: "50%", width: w } : { left: "50%", width: w }} aria-hidden="true" />
                <span className="sr-only">{c.log_odds.toFixed(3)} toward {left ? names[0] : names[1]}</span>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-4 text-[12px] text-dim">Bars add up to the forecast (log-odds). Inputs overlap, so a bar is not an independent cause.</p>
    </div>
  );
}

const ROWS: { key: string; label: string; fmt: (v: number) => string; better?: "high" | "low"; roundAware?: boolean }[] = [
  { key: "elo", label: "Elo", fmt: (v) => Math.round(v).toString(), better: "high" },
  { key: "surface_elo", label: "Surface Elo", fmt: (v) => Math.round(v).toString(), better: "high" },
  { key: "rank", label: "Ranking", fmt: (v) => Math.round(v).toString(), better: "low" },
  { key: "serve_points_won", label: "Service points won", fmt: (v) => `${(v * 100).toFixed(1)}%`, better: "high" },
  { key: "return_points_won", label: "Return points won", fmt: (v) => `${(v * 100).toFixed(1)}%`, better: "high" },
  { key: "form", label: "Form vs Elo", fmt: (v) => `${v > 0 ? "+" : ""}${(v * 100).toFixed(0)}`, better: "high" },
  { key: "days_since_last_match", label: "Days since last match", fmt: (v) => Math.round(v).toString() },
  { key: "games_won_share_this_event", label: "Games won this event", fmt: (v) => `${(v * 100).toFixed(1)}%`, better: "high", roundAware: true },
  { key: "elo_change_this_event", label: "Elo change this event", fmt: (v) => `${v > 0 ? "+" : ""}${Math.round(v)}`, better: "high", roundAware: true },
];

function Comparison({ v, names, roundAware }: { v: Version; names: readonly [string, string]; roundAware: boolean }) {
  return (
    <table className="w-full text-[13px]">
      <thead>
        <tr className="text-[12px] text-dim">
          <th className="pb-2 text-left font-normal">{familyName(names[0])}</th>
          <th className="pb-2 text-center font-normal" />
          <th className="pb-2 text-right font-normal">{familyName(names[1])}</th>
        </tr>
      </thead>
      <tbody>
        {ROWS.filter((r) => !r.roundAware || roundAware).map((r) => {
          const a = v.inputs[0][r.key] ?? null, b = v.inputs[1][r.key] ?? null;
          const aBetter = a !== null && b !== null && r.better && a !== b && (r.better === "high" ? a > b : a < b);
          const bBetter = a !== null && b !== null && r.better && a !== b && !aBetter;
          return (
            <tr key={r.key} className="border-t border-border">
              <td className={`num py-2 ${aBetter ? "font-semibold text-text" : "text-muted"}`}>{a === null ? "—" : r.fmt(a)}</td>
              <td className="py-2 text-center text-[12px] text-dim">{r.label}</td>
              <td className={`num py-2 text-right ${bBetter ? "font-semibold text-text" : "text-muted"}`}>{b === null ? "—" : r.fmt(b)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function History({ page, names }: { page: MatchPage; names: readonly [string, string] }) {
  const rows = (["tournament_start", "round_aware"] as const)
    .flatMap((k) => page.versions[k].map((v) => ({ k, v })))
    .sort((a, b) => b.v.issued_at.localeCompare(a.v.issued_at));
  if (rows.length === 0) {
    const last = page.decisions[page.decisions.length - 1];
    return <p className="px-5 py-4 text-muted">No forecast issued yet.{last ? ` ${last.text}` : ""}</p>;
  }
  return (
    <ul className="divide-y divide-border">
      {rows.map(({ k, v }) => (
        <li key={v.prediction_id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-5 py-3">
          <div>
            <p className="text-[13px]">{MODEL[k].label}</p>
            <p className="num text-[12px] text-dim"><LocalTime iso={v.issued_at} style="datetime" /></p>
          </div>
          <div className="flex items-center gap-3">
            <span className="num text-[13px] text-muted">{familyName(names[0])} {pct(v.p[0])}%</span>
            {v.counted ? <Badge tone="accent">Scored</Badge> : <Badge>{v.supersedes ? "Revision" : "Not counted"}</Badge>}
          </div>
        </li>
      ))}
    </ul>
  );
}

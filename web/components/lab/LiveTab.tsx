"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Itf, TrackRecord } from "@/lib/contract";
import type { LedgerEntry } from "@/lib/ledger";
import { favourite, pct, utcDate } from "@/lib/format";
import { LocalTime } from "../LocalTime";
import { f4, Finding, FigureStrip, pc, SectionHead, Segmented, sgn4 } from "./parts";

export type ItfLive = { entries: LedgerEntry[]; frozenAt: string | null; generatedAt: string | null };

/**
 * The live record, one model at a time. A single switch at the top chooses the model, and every section below it
 * (stage counts, activity, scores, ledger) shows that model's forecasts only, so each count matches the ledger rows
 * it filters to. The choice is kept in the address (?model=round-aware) so a link opens on the same model.
 */
type Model = "tournament_start" | "round_aware" | "itf";
const MODELS: Record<Model, { label: string; param: string; color: string; about: string }> = {
  tournament_start: { label: "Tournament start", param: "tournament-start", color: "var(--color-accent)", about: "The main Phase 4 model, for ATP and WTA matches. Protocol P1." },
  round_aware: { label: "Round-aware", param: "round-aware", color: "var(--color-neutral)", about: "Forecasts only a player's later-round ATP and WTA matches. Protocol P1." },
  itf: { label: "ITF M1", param: "itf", color: "var(--color-series-aqua)", about: "The ITF model, for ITF Men and ITF Women matches. Protocol P2." },
};
const BY_PARAM = Object.fromEntries(Object.entries(MODELS).map(([k, v]) => [v.param, k as Model])) as Record<string, Model>;

/** Stages are cumulative: every forecast is recorded, eligible ones are counted, scored ones are eligible too. */
type Stage = "Recorded" | "Eligible" | "Scored";
const isScored = (e: LedgerEntry) => e.counted && e.favourite_won !== null;
const stageOf = (e: LedgerEntry): Stage => (isScored(e) ? "Scored" : e.counted ? "Eligible" : "Recorded");
const inStage = (e: LedgerEntry, s: Stage) => s === "Recorded" || (s === "Eligible" ? e.counted : isScored(e));

type Counts = { recorded: number; eligible: number; scored: number; awaiting: number; notCompleted: number; other: number };
function countsOf(pool: LedgerEntry[]): Counts {
  const eligible = pool.filter((e) => e.counted);
  const waiting = eligible.filter((e) => !isScored(e));
  const awaiting = waiting.filter((e) => e.result_state !== "settled").length;
  const notCompleted = waiting.filter((e) => e.result_state === "settled" && e.result_status !== "completed").length;
  return { recorded: pool.length, eligible: eligible.length, scored: eligible.length - waiting.length, awaiting, notCompleted, other: waiting.length - awaiting - notCompleted };
}

function num(m: object, key: string): number | null {
  const v = (m as Record<string, unknown>)[key];
  return typeof v === "number" ? v : null;
}

export function LiveTab({ record, entries, itf, itfRecord }: {
  record: TrackRecord | null; entries: LedgerEntry[]; itf: ItfLive; itfRecord: Itf["record"] | null;
}) {
  const [model, setModel] = useState<Model>("tournament_start");
  useEffect(() => {
    const read = () => {
      const m = BY_PARAM[new URLSearchParams(window.location.search).get("model") ?? ""];
      if (m) setModel(m);
    };
    read();
  }, []);
  const choose = (m: Model) => {
    setModel(m);
    const url = new URL(window.location.href);
    if (m === "tournament_start") url.searchParams.delete("model");
    else url.searchParams.set("model", MODELS[m].param);
    window.history.replaceState(null, "", url);
  };

  const pool = useMemo(() => {
    const list = model === "itf" ? itf.entries : entries.filter((e) => e.kind === model);
    return [...list].sort((a, b) => (a.issued_at < b.issued_at ? 1 : a.issued_at > b.issued_at ? -1 : b.ledger_position - a.ledger_position));
  }, [model, entries, itf.entries]);
  const counts = useMemo(() => countsOf(pool), [pool]);
  const meta = MODELS[model];

  return (
    <div className="grid gap-12">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-card px-4 py-3">
        <span className="text-[12px] font-medium text-muted">Model</span>
        <Segmented label="Model" value={model} onChange={choose}
                   options={(Object.keys(MODELS) as Model[]).map((k) => [k, MODELS[k].label])} />
        <span className="text-[12px] text-dim">{meta.about}</span>
      </div>

      <div key={model} className="anim-fade grid gap-12">
        {model === "itf"
          ? <ItfRecord itf={itf} record={itfRecord} pool={pool} counts={counts} />
          : record
            ? <MainRecord model={model} record={record} pool={pool} counts={counts} />
            : <p className="py-10 text-muted">The live record could not be loaded.</p>}
      </div>
    </div>
  );
}

const forecastCount = (n: number) => `${n} ${n === 1 ? "forecast" : "forecasts"}`;
const matchCount = (n: number) => `${n} ${n === 1 ? "match" : "matches"}`;
const scoredTitle = (n: number) => (n === 0 ? "Recording forecasts. None scored yet." : `${forecastCount(n)} scored so far.`);

function MainRecord({ model, record, pool, counts }: { model: "tournament_start" | "round_aware"; record: TrackRecord; pool: LedgerEntry[]; counts: Counts }) {
  const meta = MODELS[model];
  return (
    <>
      <Finding kicker={`Prospective record P1 · ${meta.label}`} evidence="interim" title={scoredTitle(counts.scored)}
               aside={<Pipeline counts={counts} />}>
        {model === "round_aware" && <>The round-aware model forecasts only a player&apos;s later-round matches, so it is judged against tournament start on the same matches. </>}
        Since {utcDate(record.protocol.issued_from)}, every forecast is locked before its match and scored once a completed
        result arrives. This is the only test the model could not have been tuned on. Figures stay interim until the single
        final evaluation on or after {utcDate(record.protocol.final_evaluation_not_before)}; they decide nothing.
      </Finding>

      <section className="grid gap-5">
        <SectionHead title="Forecast activity">{meta.label} forecasts locked per day since the record began (UTC days).</SectionHead>
        <Activity entries={pool} from={record.protocol.issued_from} until={record.generated_at} color={meta.color} label={meta.label} />
      </section>

      <section className="grid gap-5 border-t border-border pt-10">
        <SectionHead title="Scores so far">
          {model === "tournament_start"
            ? "Log loss with a 95% interval, Brier score and how often the favourite won, on every scored match."
            : "Compared with tournament start on the same later-round matches. Below zero favours round-aware."}
        </SectionHead>
        {model === "tournament_start" ? <TournamentStartScores ts={record.tournament_start.all} /> : <RoundAwareScores record={record} />}
      </section>

      <section className="grid gap-5 border-t border-border pt-10">
        <Ledger entries={pool} counts={counts} label={meta.label} />
        <p className="text-[12px] text-dim">
          Counting rule: {record.protocol.counted_forecast}. Code fingerprint <span className="mono text-muted">{record.protocol.code_sha256.slice(0, 12)}</span>
          {(record.protocol.amendments ?? []).map((a) => (
            <span key={a.amendment}>, and <span className="mono text-muted">{a.code_sha256.slice(0, 12)}</span> under
              amendment {a.amendment} ({utcDate(a.created_at)})</span>
          ))}.
        </p>
      </section>
    </>
  );
}

function ItfRecord({ itf, record, pool, counts }: { itf: ItfLive; record: Itf["record"] | null; pool: LedgerEntry[]; counts: Counts }) {
  const meta = MODELS.itf;
  const first = pool.at(-1)?.issued_at ?? null;
  const last = itf.generatedAt ?? pool[0]?.issued_at ?? null;
  const frozen = itf.frozenAt ? ` on ${utcDate(itf.frozenAt)}` : "";
  return (
    <>
      <Finding kicker={`Prospective record P2 · ${meta.label}`} evidence="interim" title={scoredTitle(counts.scored)}
               aside={<Pipeline counts={counts} />}>
        Each ITF match&apos;s first M1 forecast counts, with the Elo-only forecast for the same match beside it. Forecasts
        made before P2 was frozen{frozen} are a pilot and are not scored. The ITF record is kept apart from the main-tour
        record, and while it runs every figure here is interim.
      </Finding>

      <section className="grid gap-5">
        <SectionHead title="Forecast activity">{meta.label} forecasts locked per day, pilot included (UTC days).</SectionHead>
        {first && last
          ? <Activity entries={pool} from={first} until={last} color={meta.color} label={meta.label} />
          : <p className="text-[13px] text-dim">No ITF forecast has been recorded yet.</p>}
      </section>

      <section className="grid gap-5 border-t border-border pt-10">
        <SectionHead title="Scores so far">Log loss, Brier score and how often the favourite won on every scored ITF match, with the Elo-only forecast on the same matches for reference.</SectionHead>
        <ItfScores record={record} />
      </section>

      <section className="grid gap-5 border-t border-border pt-10">
        <Ledger entries={pool} counts={counts} label={meta.label} />
        <p className="text-[12px] text-dim">
          Counting rule: each ITF match&apos;s first M1 forecast, issued after P2 was frozen{frozen}. Later forecasts for the same
          match are kept as revisions and are not scored.
        </p>
      </section>
    </>
  );
}

function TournamentStartScores({ ts }: { ts: TrackRecord["tournament_start"]["all"] }) {
  if (ts.n === 0) {
    return <p className="text-[13px] text-dim">No completed match has a counted forecast yet. No score is shown until one does.</p>;
  }
  return (
    <FigureStrip items={[
      { label: "Log loss", value: f4(num(ts, "log_loss") ?? 0), note: num(ts, "log_loss_low") !== null ? `95%: ${f4(num(ts, "log_loss_low")!)} to ${f4(num(ts, "log_loss_high")!)}` : matchCount(ts.n) },
      { label: "Brier", value: f4(num(ts, "brier") ?? 0) },
      { label: "Favourite won", value: pc(num(ts, "accuracy") ?? 0) },
      { label: "Matches", value: ts.n },
    ]} />
  );
}

/** Round-aware against tournament start on the identical later-round matches (the protocol's primary B). The figures
 *  appear only once the paired difference has a 95% interval (scored matches from at least two weeks); before that,
 *  one or two matches would make either model look far better or worse than it is. */
function RoundAwareScores({ record }: { record: TrackRecord }) {
  const pair = record.round_aware_minus_tournament_start;
  const gap = num(pair, "gap"), low = num(pair, "low"), high = num(pair, "high");
  if (pair.n === 0) {
    return <p className="text-[13px] text-dim">No later-round match with forecasts from both models has finished yet. No comparison is shown until one does.</p>;
  }
  if (gap === null || low === null || high === null) {
    return (
      <p className="text-[13px] text-dim">
        {matchCount(pair.n)} with forecasts from both models {pair.n === 1 ? "has" : "have"} finished so far: too few to
        compare the two models. The comparison appears once scored matches span at least two weeks, when the difference
        has a 95% interval.
      </p>
    );
  }
  return (
    <FigureStrip items={[
      { label: "Difference", value: sgn4(gap), note: `95%: ${sgn4(low)} to ${sgn4(high)}` },
      { label: "Round-aware log loss", value: f4(num(record.round_aware.all, "log_loss") ?? 0) },
      { label: "Tournament start", value: f4(num(record.tournament_start_on_same_matches, "log_loss") ?? 0), note: "Log loss, same matches" },
      { label: "Matches", value: pair.n, note: `${num(pair, "weeks") ?? 0} weeks` },
    ]} />
  );
}

function ItfScores({ record }: { record: Itf["record"] | null }) {
  if (!record) return <p className="text-[13px] text-dim">The ITF record could not be loaded.</p>;
  const m1 = record.m1, elo = record.elo;
  if (m1.matches === 0 || m1.log_loss === null) {
    return <p className="text-[13px] text-dim">No completed ITF match has a counted forecast yet. No score is shown until one does.</p>;
  }
  return (
    <FigureStrip items={[
      { label: "M1 log loss", value: f4(m1.log_loss) },
      { label: "Elo-only log loss", value: elo.log_loss !== null ? f4(elo.log_loss) : "–", note: "Same matches" },
      { label: "Brier", value: m1.brier !== null ? f4(m1.brier) : "–" },
      { label: "Favourite won", value: m1.accuracy !== null ? pc(m1.accuracy) : "–" },
      { label: "Matches", value: m1.matches.toLocaleString("en-GB") },
    ]} />
  );
}

/** The record's stages in the counted colour (lavender), each step fainter than the one before. */
function Pipeline({ counts }: { counts: Counts }) {
  const max = Math.max(counts.recorded, 1);
  const stages: [string, number, string][] = [
    ["Recorded", counts.recorded, "Locked in the ledger"],
    ["Eligible", counts.eligible, "Counted under the frozen rules"],
    ["Scored", counts.scored, "Completed match, result attached"],
  ];
  const waiting = [
    counts.awaiting > 0 && `${counts.awaiting} awaiting a result`,
    counts.notCompleted > 0 && `${counts.notCompleted} not completed (retirement, walkover or similar)`,
    counts.other > 0 && `${counts.other} settled without a scorable result`,
  ].filter(Boolean);
  return (
    <div className="grid gap-3">
      {stages.map(([label, n, note], i) => (
        <div key={label} className="grid grid-cols-[84px_minmax(0,1fr)_48px] items-center gap-3">
          <span className="text-[12px] text-muted">{label}</span>
          <div className="h-6 overflow-hidden rounded bg-track/60" title={note}>
            <div className="anim-fill h-full rounded" style={{ width: `${(n / max) * 100}%`, background: "var(--color-counted)", opacity: 1 - i * 0.25, animationDelay: `${i * 120}ms` }} />
          </div>
          <span className="fig text-right text-[15px]">{n.toLocaleString("en-GB")}</span>
        </div>
      ))}
      {waiting.length > 0 && <p className="pl-[96px] text-[12px] text-dim">Eligible, not yet scored: {waiting.join("; ")}.</p>}
    </div>
  );
}

function Activity({ entries, from, until, color, label }: { entries: LedgerEntry[]; from: string; until: string; color: string; label: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const days = useMemo(() => {
    const start = Date.UTC(+from.slice(0, 4), +from.slice(5, 7) - 1, +from.slice(8, 10));
    const end = Date.UTC(+until.slice(0, 4), +until.slice(5, 7) - 1, +until.slice(8, 10));
    const list: { day: string; n: number }[] = [];
    for (let t = start; t <= end; t += 86_400_000) list.push({ day: new Date(t).toISOString().slice(0, 10), n: 0 });
    const at = new Map(list.map((d, i) => [d.day, i]));
    for (const e of entries) {
      const i = at.get(e.issued_at.slice(0, 10));
      if (i !== undefined) list[i]!.n += 1;
    }
    return list;
  }, [entries, from, until]);
  const max = Math.max(1, ...days.map((d) => d.n));
  const H = 140;
  const noun = (n: number) => `${n} ${n === 1 ? "forecast" : "forecasts"}`;
  return (
    <div>
      <div className="relative overflow-x-auto border-b border-border-strong" tabIndex={0} role="region" aria-label={`${label} forecasts per day`}>
        <div className="flex h-[150px] min-w-full items-end gap-1.5 pb-px">
          {days.map((d, i) => (
            <button key={d.day} type="button" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
                    aria-label={`${d.day}: ${noun(d.n)}`}
                    className="group flex h-full w-7 shrink-0 flex-col justify-end rounded-t-sm">
              {d.n > 0
                ? <span className="anim-fade block w-full rounded-t-sm" style={{ height: `${(d.n / max) * H}px`, background: color, opacity: hover === null || hover === i ? 1 : 0.4 }} />
                : <span className="block h-px w-full bg-border-strong" />}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-2 flex justify-between text-[11px] text-dim">
        <span className="fig">{days[0]?.day}</span>
        <span className="fig text-muted">{hover !== null ? `${days[hover]!.day}: ${noun(days[hover]!.n)}` : `${days.length} day${days.length === 1 ? "" : "s"} of the record so far`}</span>
        <span className="fig">{days.at(-1)?.day}</span>
      </p>
    </div>
  );
}

const PAGE = 50;

function Ledger({ entries, counts, label }: { entries: LedgerEntry[]; counts: Counts; label: string }) {
  const [q, setQ] = useState("");
  const [stage, setStage] = useState<Stage>("Recorded");
  const [limit, setLimit] = useState(PAGE);
  const query = q.trim().toLowerCase();
  const rows = entries.filter((e) => inStage(e, stage)
    && (!query || [e.players[0], e.players[1], e.event, e.prediction_id, e.model_version].some((s) => (s ?? "").toLowerCase().includes(query))));
  const shown = rows.slice(0, limit);
  const option = (s: Stage, text: string, n: number): [Stage, React.ReactNode] =>
    [s, <span key={s} className="inline-flex items-baseline gap-1.5">{text}<span className="fig text-[11px] text-dim">{n.toLocaleString("en-GB")}</span></span>];
  return (
    <>
      <SectionHead title="Prediction ledger" action={
        <div className="flex flex-wrap items-center gap-2">
          <label>
            <span className="sr-only">Search the ledger</span>
            <input id="ledger-search" value={q} onChange={(e) => { setQ(e.target.value); setLimit(PAGE); }} placeholder="Player, event or id"
                   className="w-[200px] rounded-md border border-border bg-bg px-2.5 py-1.5 text-[12px] outline-none placeholder:text-dim focus:border-accent" />
          </label>
          <Segmented label="Stage" value={stage} onChange={(s) => { setStage(s); setLimit(PAGE); }}
                     options={[option("Recorded", "All recorded", counts.recorded), option("Eligible", "Eligible", counts.eligible), option("Scored", "Scored", counts.scored)]} />
        </div>
      }>
        Every {label} forecast since the record began, newest first. Eligible includes the scored forecasts, so each
        count matches the figures above.
      </SectionHead>
      <div className="overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label={`${label} prediction ledger`}>
        <table className="w-full min-w-[760px] text-[13px]">
          <thead>
            <tr className="border-b border-border bg-card text-left text-[11px] text-dim">
              <th className="px-4 py-2.5 font-normal">Locked</th><th className="px-3 py-2.5 font-normal">Match</th>
              <th className="px-3 py-2.5 font-normal">Favourite</th><th className="px-3 py-2.5 font-normal">Model</th>
              <th className="px-3 py-2.5 font-normal">Stage</th><th className="px-4 py-2.5 text-right font-normal">Chain</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {shown.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-muted">No forecasts match.</td></tr>
            ) : shown.map((e) => {
              const fav = favourite(e.p);
              const s = stageOf(e);
              return (
                <tr key={e.prediction_id} className="transition-colors hover:bg-card">
                  <td className="fig whitespace-nowrap px-4 py-2.5 text-[12px] text-muted"><LocalTime iso={e.issued_at} style="datetime" /></td>
                  <td className="px-3 py-2.5"><Link href={`/matches/${e.match_uid}`} className="hover:text-accent">{e.players[0]} v {e.players[1]}</Link><p className="text-[11px] text-dim">{e.event}</p></td>
                  <td className="fig px-3 py-2.5 text-[12px]">{fav !== null ? `${(e.players[fav] ?? "").split(" ").slice(-1)[0]} ${pct(e.p[fav])}%` : "50 / 50"}</td>
                  <td className="mono px-3 py-2.5 text-muted">{e.model_version}</td>
                  <td className="px-3 py-2.5">
                    <span className="text-[12px] text-counted">{s}</span>
                    {s === "Scored" && <span className={`ml-2 text-[11px] ${e.favourite_won ? "text-pos" : "text-neg"}`}>{e.favourite_won ? "favourite won" : "upset"}</span>}
                  </td>
                  <td className="mono px-4 py-2.5 text-right text-dim" title={e.record_hash}>#{e.ledger_position} {e.record_hash.slice(0, 8)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > PAGE && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-[12px] text-dim">
          <span className="fig">Showing {shown.length.toLocaleString("en-GB")} of {rows.length.toLocaleString("en-GB")}</span>
          {shown.length < rows.length && (
            <span className="flex gap-2">
              <button type="button" onClick={() => setLimit((l) => l + PAGE)} className="rounded-md border border-border-strong px-3 py-1.5 text-muted transition-colors hover:text-text">Show {Math.min(PAGE, rows.length - shown.length)} more</button>
              <button type="button" onClick={() => setLimit(rows.length)} className="rounded-md px-3 py-1.5 text-muted transition-colors hover:text-text">Show all</button>
            </span>
          )}
        </div>
      )}
    </>
  );
}

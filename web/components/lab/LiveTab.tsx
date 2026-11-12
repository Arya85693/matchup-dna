"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { ArchiveEntry, TrackRecord } from "@/lib/contract";
import { favourite, pct, utcDate } from "@/lib/format";
import { LocalTime } from "../LocalTime";
import { f4, Finding, FigureStrip, pc, SectionHead, Segmented, sgn4 } from "./parts";

const NEUTRAL = "var(--color-neutral)";
type Stage = "Scored" | "Eligible" | "Recorded";

function stageOf(e: ArchiveEntry): Stage {
  if (e.counted && e.favourite_won !== null) return "Scored";
  return e.counted ? "Eligible" : "Recorded";
}

function num(m: object, key: string): number | null {
  const v = (m as Record<string, unknown>)[key];
  return typeof v === "number" ? v : null;
}

export function LiveTab({ record, entries }: { record: TrackRecord | null; entries: ArchiveEntry[] }) {
  const [model, setModel] = useState<Model>("tournament_start");
  if (!record) return <p className="py-10 text-muted">The live record could not be loaded.</p>;
  const c = record.counts;
  const sum = (o: Record<string, number>) => Object.values(o).reduce((a, b) => a + b, 0);
  const recorded = sum(c.issued), eligible = sum(c.counted), scored = sum(c.scored);
  const ts = record.tournament_start.all;
  const scoredTs = c.scored.tournament_start ?? 0, scoredRa = c.scored.round_aware ?? 0;

  return (
    <div className="grid gap-12">
      <Finding kicker="Prospective record P1" evidence="interim"
        title={scored === 0 ? "Recording forecasts. None scored yet." : `${scored} forecasts scored so far.`}
        aside={<Pipeline recorded={recorded} eligible={eligible} scored={scored} excluded={c.excluded} />}>
        {scored > 0 && <>{forecastCount(scoredTs)} from the tournament-start model and {forecastCount(scoredRa)} from the
          round-aware model, which forecasts only a player&apos;s later-round matches; a match can count once for each. </>}
        Since {utcDate(record.protocol.issued_from)}, every forecast is locked before its match and scored once a completed
        result arrives. This is the only test the model could not have been tuned on. Figures stay interim until the single
        final evaluation on or after {utcDate(record.protocol.final_evaluation_not_before)}; they decide nothing.
      </Finding>

      <section className="grid gap-5">
        <SectionHead title="Forecast activity">Forecasts locked per day since the record began, by model (UTC days).</SectionHead>
        <Activity entries={entries} from={record.protocol.issued_from} until={record.generated_at} />
      </section>

      <section className="grid gap-5 border-t border-border pt-10">
        <SectionHead title="Scores so far"
          action={<Segmented label="Model" value={model} onChange={setModel}
                             options={[["tournament_start", "Tournament start"], ["round_aware", "Round-aware"]]} />}>
          {model === "tournament_start"
            ? "The tournament-start model, the main Phase 4 model: log loss with a 95% interval, Brier score and how often the favourite won, on every scored match."
            : "Round-aware forecasts only later-round matches, so it is compared with tournament start on the same matches. Below zero favours round-aware."}
        </SectionHead>
        {model === "tournament_start" ? <TournamentStartScores ts={ts} /> : <RoundAwareScores record={record} />}
      </section>

      <section className="grid gap-5 border-t border-border pt-10">
        <Ledger entries={entries} />
        <p className="text-[12px] text-dim">
          Counting rule: {record.protocol.counted_forecast}. Code fingerprint <span className="mono text-muted">{record.protocol.code_sha256.slice(0, 12)}</span>
          {(record.protocol.amendments ?? []).map((a) => (
            <span key={a.amendment}>, and <span className="mono text-muted">{a.code_sha256.slice(0, 12)}</span> under
              amendment {a.amendment} ({utcDate(a.created_at)})</span>
          ))}.
        </p>
      </section>
    </div>
  );
}

type Model = "tournament_start" | "round_aware";

const forecastCount = (n: number) => `${n} ${n === 1 ? "forecast" : "forecasts"}`;
const matchCount = (n: number) => `${n} ${n === 1 ? "match" : "matches"}`;

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

function Pipeline({ recorded, eligible, scored, excluded }: { recorded: number; eligible: number; scored: number; excluded: { reason: string; n: number }[] }) {
  const max = Math.max(recorded, 1);
  const stages: [string, number, string][] = [
    ["Recorded", recorded, "Locked in the ledger"],
    ["Eligible", eligible, "Counted under the frozen rules"],
    ["Scored", scored, "Completed match, result attached"],
  ];
  return (
    <div className="grid gap-3">
      {stages.map(([label, n, note], i) => (
        <div key={label} className="grid grid-cols-[84px_minmax(0,1fr)_40px] items-center gap-3">
          <span className="text-[12px] text-muted">{label}</span>
          <div className="h-6 overflow-hidden rounded bg-track/60" title={note}>
            <div className="anim-fill h-full rounded bg-accent" style={{ width: `${(n / max) * 100}%`, opacity: 1 - i * 0.25, animationDelay: `${i * 120}ms` }} />
          </div>
          <span className="fig text-right text-[15px]">{n}</span>
        </div>
      ))}
      {excluded.length > 0 && <p className="pl-[96px] text-[12px] text-dim">Waiting: {excluded.map((e) => `${e.reason} (${e.n})`).join("; ")}</p>}
    </div>
  );
}

function Activity({ entries, from, until }: { entries: ArchiveEntry[]; from: string; until: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const days = useMemo(() => {
    const start = Date.UTC(+from.slice(0, 4), +from.slice(5, 7) - 1, +from.slice(8, 10));
    const end = Date.UTC(+until.slice(0, 4), +until.slice(5, 7) - 1, +until.slice(8, 10));
    const list: { day: string; ts: number; ra: number }[] = [];
    for (let t = start; t <= end; t += 86_400_000) list.push({ day: new Date(t).toISOString().slice(0, 10), ts: 0, ra: 0 });
    for (const e of entries) {
      if (e.issued_at < from) continue;
      const d = list.find((x) => x.day === e.issued_at.slice(0, 10));
      if (d) d[e.kind === "tournament_start" ? "ts" : "ra"] += 1;
    }
    return list;
  }, [entries, from, until]);
  const max = Math.max(1, ...days.map((d) => d.ts + d.ra));
  const H = 140;
  return (
    <div>
      <div className="mb-3 flex gap-4 text-[12px] text-muted">
        <span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-sm bg-accent" />Tournament start</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-sm" style={{ background: NEUTRAL }} />Round-aware</span>
      </div>
      <div className="relative overflow-x-auto border-b border-border-strong" tabIndex={0} role="region" aria-label="Forecasts per day">
        <div className="flex h-[150px] min-w-full items-end gap-1.5 pb-px">
          {days.map((d, i) => (
            <button key={d.day} type="button" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
                    aria-label={`${d.day}: ${d.ts} tournament-start, ${d.ra} round-aware`}
                    className="group flex h-full w-7 shrink-0 flex-col justify-end rounded-t-sm">
              <span className="anim-fade block w-full rounded-t-sm" style={{ height: `${(d.ra / max) * H}px`, background: NEUTRAL, opacity: hover === null || hover === i ? 1 : 0.4 }} />
              <span className="anim-fade block w-full bg-accent" style={{ height: `${(d.ts / max) * H}px`, opacity: hover === null || hover === i ? 1 : 0.4 }} />
              {d.ts + d.ra === 0 && <span className="block h-px w-full bg-border-strong" />}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-2 flex justify-between text-[11px] text-dim">
        <span className="fig">{days[0]?.day}</span>
        <span className="fig text-muted">{hover !== null ? `${days[hover]!.day}: ${days[hover]!.ts} tournament start, ${days[hover]!.ra} round-aware` : `${days.length} day${days.length === 1 ? "" : "s"} of the record so far`}</span>
        <span className="fig">{days.at(-1)?.day}</span>
      </p>
    </div>
  );
}

function Ledger({ entries }: { entries: ArchiveEntry[] }) {
  const [q, setQ] = useState("");
  const [stage, setStage] = useState<"All" | Stage>("All");
  const rows = entries.filter((e) => {
    if (stage !== "All" && stageOf(e) !== stage) return false;
    const query = q.trim().toLowerCase();
    return !query || [e.players[0], e.players[1], e.event, e.prediction_id, e.model_version].some((s) => (s ?? "").toLowerCase().includes(query));
  });
  return (
    <>
      <SectionHead title="Prediction ledger" action={
        <div className="flex flex-wrap items-center gap-2">
          <label>
            <span className="sr-only">Search the ledger</span>
            <input id="ledger-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Player, event or id"
                   className="w-[200px] rounded-md border border-border bg-bg px-2.5 py-1.5 text-[12px] outline-none placeholder:text-dim focus:border-accent" />
          </label>
          <Segmented label="Stage" value={stage} onChange={setStage} options={[["All", "All"], ["Recorded", "Recorded"], ["Eligible", "Eligible"], ["Scored", "Scored"]]} />
        </div>
      }>Every forecast since the record began, newest first.</SectionHead>
      <div className="overflow-x-auto rounded-lg border border-border" tabIndex={0} role="region" aria-label="Prediction ledger">
        <table className="w-full min-w-[760px] text-[13px]">
          <thead>
            <tr className="border-b border-border bg-card text-left text-[11px] text-dim">
              <th className="px-4 py-2.5 font-normal">Locked</th><th className="px-3 py-2.5 font-normal">Match</th>
              <th className="px-3 py-2.5 font-normal">Favourite</th><th className="px-3 py-2.5 font-normal">Model</th>
              <th className="px-3 py-2.5 font-normal">Stage</th><th className="px-4 py-2.5 text-right font-normal">Chain</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-muted">No forecasts match.</td></tr>
            ) : rows.map((e) => {
              const fav = favourite(e.p);
              const s = stageOf(e);
              return (
                <tr key={e.prediction_id} className="transition-colors hover:bg-card">
                  <td className="fig whitespace-nowrap px-4 py-2.5 text-[12px] text-muted"><LocalTime iso={e.issued_at} style="datetime" /></td>
                  <td className="px-3 py-2.5"><Link href={`/matches/${e.match_uid}`} className="hover:text-accent">{e.players[0]} v {e.players[1]}</Link><p className="text-[11px] text-dim">{e.event}</p></td>
                  <td className="fig px-3 py-2.5 text-[12px]">{fav !== null ? `${(e.players[fav] ?? "").split(" ").slice(-1)[0]} ${pct(e.p[fav])}%` : "50 / 50"}</td>
                  <td className="mono px-3 py-2.5 text-muted">{e.model_version}</td>
                  <td className="px-3 py-2.5">
                    <span className={`text-[12px] ${s === "Scored" ? "text-text" : s === "Eligible" ? "text-accent" : "text-dim"}`}>{s}</span>
                    {s === "Scored" && <span className={`ml-2 text-[11px] ${e.favourite_won ? "text-pos" : "text-neg"}`}>{e.favourite_won ? "favourite won" : "upset"}</span>}
                  </td>
                  <td className="mono px-4 py-2.5 text-right text-dim" title={e.record_hash}>#{e.ledger_position} {e.record_hash.slice(0, 8)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}


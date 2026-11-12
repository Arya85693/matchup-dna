"use client";

import Link from "next/link";
import { Fragment, useMemo, useState } from "react";
import type { ArchiveEntry } from "@/lib/contract";
import { FEATURES, featureLabel } from "@/lib/features";
import { circuitLabel, familyName, favourite, pct, roundLabel, STATE_LABELS } from "@/lib/format";
import { FigureStrip, Segmented } from "../lab/parts";
import { LocalTime } from "../LocalTime";
import { ProbabilitySplit } from "../match/parts";
import { Badge } from "../ui";

type Kind = ArchiveEntry["kind"];
const MODEL_LABEL: Record<Kind, string> = { tournament_start: "Tournament start", round_aware: "Round-aware" };
/** ITF forecasts come from one model (ITF M1, a tournament-start model). */
const isItf = (e: ArchiveEntry) => e.model_version.startsWith("itf-");
const modelLabel = (k: Kind, itf: boolean) => (itf ? "ITF model (M1)" : MODEL_LABEL[k]);

/** Issuance: was this the counted (first) forecast, a later revision, or neither? */
function issuance(e: ArchiveEntry): { label: string; tone: "counted" | "neutral" } {
  if (e.counted) return { label: "Counted (first issued)", tone: "counted" };
  return { label: e.supersedes ? "Superseding revision" : "Not counted", tone: "neutral" };
}
/** Settlement: has a result been recorded, and do the sources agree? */
function settlement(e: ArchiveEntry): { label: string; tone: "neutral" | "warn" | "pos" } {
  if (e.result_state === "conflict") return { label: "Result under review", tone: "warn" };
  if (e.result_state === "settled") return { label: STATE_LABELS[e.result_status ?? ""] ?? e.result_status ?? "Settled", tone: "neutral" };
  return { label: "Awaiting result", tone: "neutral" };
}
/** Evaluation under the frozen protocol: only counted forecasts of completed matches are scored. */
type Eval = "scored" | "excluded" | "pending" | "not_counted";
function evaluation(e: ArchiveEntry): Eval {
  if (!e.counted) return "not_counted";
  if (e.result_state === "settled" && e.result_status === "completed") return "scored";
  if (e.result_state === "settled") return "excluded";
  return "pending";
}
const EVAL_LABEL: Record<Eval, string> = { scored: "Scored", excluded: "Excluded (not completed)", pending: "Pending", not_counted: "Not evaluated" };

type SortKey = "position" | "issued" | "start" | "prob";

/** The forecast archive. `circuit="itf"` is the same view for ITF forecasts: ITF Men and ITF Women, and one model
 * (ITF M1, a tournament-start model), so there is no model filter. */
export function ArchiveView({ entries, circuit = "main" }: { entries: ArchiveEntry[]; circuit?: "main" | "itf" }) {
  const itf = circuit === "itf";
  const [view, setView] = useState<"matches" | "ledger">("matches");
  const [q, setQ] = useState("");
  const [model, setModel] = useState<"all" | Kind>("all");
  const [state, setState] = useState<"all" | Eval>("all");
  const [tour, setTour] = useState<"all" | "ATP" | "WTA">("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "position", dir: -1 });
  const [open, setOpen] = useState<string | null>(null);

  const kpis = useMemo(() => {
    const matches = new Set(entries.map((e) => e.match_uid)).size;
    const counted = entries.filter((e) => e.counted);
    const settled = new Set(entries.filter((e) => e.result_state === "settled").map((e) => e.match_uid)).size;
    const scored = counted.filter((e) => evaluation(e) === "scored");
    const favWon = scored.filter((e) => e.favourite_won === true).length;
    return { matches, counted: counted.length, settled, scored, favWon, revisions: entries.filter((e) => e.supersedes).length };
  }, [entries]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    return entries.filter((e) => (model === "all" || e.kind === model) && (tour === "all" || e.tour === tour)
      && (state === "all" || evaluation(e) === state)
      && (!query || [e.players[0], e.players[1], e.event, e.prediction_id, e.model_version, e.record_hash].some((s) => (s ?? "").toLowerCase().includes(query))));
  }, [entries, q, model, tour, state]);

  const sorted = useMemo(() => {
    const val = (e: ArchiveEntry): number | string => sort.key === "position" ? e.ledger_position : sort.key === "issued" ? e.issued_at
      : sort.key === "start" ? (e.scheduled_start ?? "") : Math.max(...e.p);
    return [...filtered].sort((a, b) => (val(a) < val(b) ? -1 : val(a) > val(b) ? 1 : 0) * sort.dir);
  }, [filtered, sort]);

  const byTournament = useMemo(() => {
    const events = new Map<string, Map<string, ArchiveEntry[]>>();
    for (const e of [...filtered].sort((a, b) => (b.scheduled_start ?? "").localeCompare(a.scheduled_start ?? ""))) {
      const key = `${isItf(e) ? circuitLabel(e.tour, null, "itf") : e.tour} · ${e.event}`;
      if (!events.has(key)) events.set(key, new Map());
      const m = events.get(key)!;
      m.set(e.match_uid, [...(m.get(e.match_uid) ?? []), e]);
    }
    return [...events.entries()];
  }, [filtered]);

  const sortBy = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: -1 }));
  const header = (key: SortKey, label: string, cls = "") => (
    <th scope="col" aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className={`px-3 py-2.5 font-normal ${cls}`}>
      <button type="button" onClick={() => sortBy(key)} className={`inline-flex items-center gap-1 ${sort.key === key ? "text-text" : "hover:text-text"}`}>
        {label}<span aria-hidden="true" className={sort.key === key ? "text-accent" : "text-border-strong"}>{sort.key === key && sort.dir === 1 ? "▲" : "▼"}</span>
      </button>
    </th>
  );

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <FigureStrip items={[
        { label: "Forecasts recorded", value: entries.length, note: `${kpis.revisions} superseding revision${kpis.revisions === 1 ? "" : "s"}` },
        { label: "Matches covered", value: kpis.matches },
        { label: "Counted (first issued)", value: kpis.counted, note: "Under the frozen protocol" },
        { label: "Matches settled", value: kpis.settled },
        { label: "Scored", value: kpis.scored.length, note: kpis.scored.length ? `Favourite won ${kpis.favWon} of ${kpis.scored.length} (interim)` : "None yet" },
      ]} />

      <div className="grid gap-3 rounded-lg border border-border bg-card/50 p-3">
        <div className="flex flex-wrap items-center gap-3">
          <Segmented label="View" value={view} onChange={(v) => { setView(v); setOpen(null); }} options={[["matches", "By match"], ["ledger", "Ledger records"]]} />
          <label className="relative min-w-[200px] flex-1">
            <span className="sr-only">Search the archive</span>
            <input id="archive-search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Player, tournament, prediction id or hash" autoComplete="off"
                   className="w-full rounded-md border border-border bg-bg px-3 py-1.5 text-[13px] outline-none placeholder:text-dim focus:border-accent" />
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px]">
          <Segmented label="Tour" value={tour} onChange={setTour}
                     options={itf ? [["all", "All ITF"], ["ATP", "ITF Men"], ["WTA", "ITF Women"]] : [["all", "All tours"], ["ATP", "ATP"], ["WTA", "WTA"]]} />
          {!itf && <Segmented label="Model" value={model} onChange={setModel} options={[["all", "Both models"], ["tournament_start", "Tournament start"], ["round_aware", "Round-aware"]]} />}
          <label className="flex items-center gap-2">
            <span className="text-dim">Evaluation</span>
            <select id="archive-state" value={state} onChange={(e) => setState(e.target.value as typeof state)} className="rounded-md border border-border bg-bg px-2 py-1 text-[12px] text-text">
              <option value="all">Any</option>
              {(Object.keys(EVAL_LABEL) as Eval[]).map((k) => <option key={k} value={k}>{EVAL_LABEL[k]}</option>)}
            </select>
          </label>
          <span className="fig ml-auto text-dim" aria-live="polite">{filtered.length} of {entries.length} records</span>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border-strong px-6 py-12 text-center text-[13px] text-muted">
          No forecasts match. <button type="button" className="link" onClick={() => { setQ(""); setModel("all"); setState("all"); setTour("all"); }}>Clear filters</button>
        </div>
      ) : view === "matches" ? (
        <div className="grid gap-6">
          {byTournament.map(([event, matches]) => (
            <section key={event} aria-label={event} className="overflow-hidden rounded-lg border border-border">
              <h2 className="border-b border-border bg-card px-4 py-2.5 text-[13px] font-medium">{event}</h2>
              <ul className="divide-y divide-border">
                {[...matches.entries()].map(([uid, list]) => <MatchRecord key={uid} uid={uid} list={list} open={open} setOpen={setOpen} />)}
              </ul>
            </section>
          ))}
        </div>
      ) : (
        <div className="relative overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[900px] text-[13px]">
            <thead className="bg-card text-left text-[11px] text-dim">
              <tr className="border-b border-border">
                {header("position", "#")}{header("issued", "Issued")}<th scope="col" className="px-3 py-2.5 font-normal">Match</th>
                <th scope="col" className="px-3 py-2.5 font-normal">Model</th>{header("prob", "Forecast")}
                <th scope="col" className="px-3 py-2.5 font-normal">Issuance</th><th scope="col" className="px-3 py-2.5 font-normal">Settlement</th>
                <th scope="col" className="px-3 py-2.5 font-normal">Evaluation</th><th scope="col" className="px-3 py-2.5"><span className="sr-only">Inspect</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sorted.map((e) => {
                const isOpen = open === e.prediction_id;
                const fav = favourite(e.p);
                const ev = evaluation(e);
                return (
                  <Fragment key={e.prediction_id}>
                    <tr className={`transition-colors hover:bg-card ${isOpen ? "bg-card" : ""}`}>
                      <td className="mono px-3 py-2.5 text-dim">{e.ledger_position}</td>
                      <td className="fig whitespace-nowrap px-3 py-2.5 text-[12px] text-muted"><LocalTime iso={e.issued_at} style="datetime" /></td>
                      <td className="px-3 py-2.5"><Link href={`/matches/${e.match_uid}`} className="hover:text-accent">{e.players[0]} v {e.players[1]}</Link><p className="text-[11px] text-dim">{e.event} · {roundLabel(e.round)}</p></td>
                      <td className="mono px-3 py-2.5 text-muted">{e.model_version}</td>
                      <td className="w-[150px] px-3 py-2.5">
                        <p className="fig text-[12px]">{fav !== null ? `${familyName(e.players[fav])} ${pct(e.p[fav])}%` : "50 / 50"}</p>
                        <div className="mt-1"><ProbabilitySplit p={e.p} height={4} animate={false} showTick={false} /></div>
                      </td>
                      <td className="px-3 py-2.5"><Badge tone={issuance(e).tone}>{issuance(e).label}</Badge></td>
                      <td className="px-3 py-2.5"><Badge tone={settlement(e).tone}>{settlement(e).label}</Badge></td>
                      <td className="px-3 py-2.5 text-[12px]"><EvalCell e={e} ev={ev} /></td>
                      <td className="px-3 py-2.5 text-right">
                        <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : e.prediction_id)} className="rounded-md border border-border px-2 py-1 text-[12px] text-muted hover:text-text">
                          {isOpen ? "Close" : "Inspect"}
                        </button>
                      </td>
                    </tr>
                    {isOpen && <tr><td colSpan={9} className="bg-bg px-4 py-4"><Inspect e={e} /></td></tr>}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-[12px] text-dim">
        Forecasts are never edited or deleted, and each model&apos;s forecasts stay separate. Only the first forecast per match and
        model, issued at least 30 minutes before the start, counts in the prospective record; later versions are kept and
        labelled as revisions. Verification shows a forecast was recorded unchanged, not that it was right.
      </p>
    </div>
  );
}

function EvalCell({ e, ev }: { e: ArchiveEntry; ev: Eval }) {
  // Scored is a counting status (lavender); the result beside it keeps its own colour.
  if (ev === "scored") {
    return (
      <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
        <Badge tone="counted">Scored</Badge>
        {e.favourite_won !== null && <span className={`whitespace-nowrap text-[12px] ${e.favourite_won ? "text-pos" : "text-neg"}`}>{e.favourite_won ? "favourite won" : "upset"}</span>}
      </span>
    );
  }
  return <span className={ev === "pending" ? "text-muted" : "text-dim"}>{EVAL_LABEL[ev]}</span>;
}

/** One match with every stored forecast of both models, grouped by model, newest version last. */
function MatchRecord({ uid, list, open, setOpen }: { uid: string; list: ArchiveEntry[]; open: string | null; setOpen: (id: string | null) => void }) {
  const first = list[0]!;
  const byModel = (["tournament_start", "round_aware"] as Kind[]).map((k) => ({ k, versions: list.filter((e) => e.kind === k).sort((a, b) => a.ledger_position - b.ledger_position) }));
  const inspected = list.find((e) => e.prediction_id === open);
  return (
    <li className="px-4 py-3.5">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,2fr)] lg:items-start">
        <div className="min-w-0">
          <Link href={`/matches/${uid}`} className="font-medium hover:text-accent">{first.players[0]} v {first.players[1]}</Link>
          <p className="mt-0.5 text-[12px] text-dim">{roundLabel(first.round)} · {first.scheduled_start ? <LocalTime iso={first.scheduled_start} style="datetime" /> : "start unknown"}</p>
          <div className="mt-2 flex flex-wrap gap-1.5"><Badge tone={settlement(first).tone}>{settlement(first).label}</Badge></div>
        </div>
        <div className="grid gap-2">
          {byModel.filter(({ k }) => !isItf(first) || k === "tournament_start").map(({ k, versions }) => (
            <div key={k} className="grid gap-1.5 sm:grid-cols-[120px_minmax(0,1fr)] sm:items-start">
              <span className="pt-1 text-[12px] text-muted">{modelLabel(k, isItf(first))}</span>
              {versions.length === 0 ? <span className="pt-1 text-[12px] text-dim">No forecast issued</span> : (
                <ul className="grid gap-1.5">
                  {versions.map((e) => {
                    const fav = favourite(e.p);
                    const isOpen = open === e.prediction_id;
                    return (
                      <li key={e.prediction_id}>
                        <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : e.prediction_id)}
                                className={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-md border px-3 py-2 text-left transition-colors sm:grid-cols-[150px_minmax(0,1fr)_auto] ${isOpen ? "border-border-strong bg-card" : "border-border hover:bg-card"}`}>
                          <span className="fig text-[12px]">{fav !== null ? `${familyName(e.players[fav])} ${pct(e.p[fav])}%` : "50 / 50"}</span>
                          <span className="col-span-2 sm:col-span-1 sm:col-start-2 sm:row-start-1"><ProbabilitySplit p={e.p} height={4} animate={false} showTick={false} /></span>
                          <span className="col-start-2 row-start-1 flex items-center gap-1.5 sm:col-start-3">
                            <Badge tone={issuance(e).tone}>{e.counted ? "Counted" : e.supersedes ? "Revision" : "Not counted"}</Badge>
                            <EvalCell e={e} ev={evaluation(e)} />
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          ))}
        </div>
      </div>
      {inspected && <div className="mt-3 rounded-lg border border-border bg-bg p-4"><Inspect e={inspected} /></div>}
    </li>
  );
}

/** Everything stored with one forecast: version, times, probabilities, feature snapshot and verification. */
function Inspect({ e }: { e: ArchiveEntry }) {
  const max = Math.max(0.2, ...e.contributions.map(([, v]) => Math.abs(v)));
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="grid content-start gap-4">
        <dl className="grid grid-cols-[130px_minmax(0,1fr)] gap-y-1.5 text-[12px]">
          <dt className="text-dim">Model</dt><dd>{modelLabel(e.kind, isItf(e))} <span className="mono text-muted">{e.model_version}</span></dd>
          <dt className="text-dim">Issued</dt><dd className="fig"><LocalTime iso={e.issued_at} style="datetime" /> {e.issued_before_start && <span className="text-pos">· before the scheduled start</span>}</dd>
          <dt className="text-dim">Scheduled start</dt><dd className="fig">{e.scheduled_start ? <LocalTime iso={e.scheduled_start} style="datetime" /> : "—"}</dd>
          <dt className="text-dim">Forecast</dt><dd className="fig">{familyName(e.players[0])} {pct(e.p[0])}% · {familyName(e.players[1])} {pct(e.p[1])}%</dd>
          <dt className="text-dim">Status</dt><dd>{issuance(e).label}; {settlement(e).label.toLowerCase()}; {EVAL_LABEL[evaluation(e)].toLowerCase()}</dd>
        </dl>
        <div>
          <p className="mb-2 text-[12px] text-muted">Feature snapshot <span className="text-dim">(model inputs and their log-odds push toward {familyName(e.players[0])})</span></p>
          <table className="w-full text-[12px]">
            <thead><tr className="text-left text-[11px] text-dim"><th className="py-1 font-normal">Input</th><th className="py-1 text-right font-normal">Value</th><th className="w-[38%] py-1 text-right font-normal">Contribution</th></tr></thead>
            <tbody>
              {e.contributions.map(([k, v]) => (
                <tr key={k} className="border-t border-border" title={FEATURES[k]?.help}>
                  <td className="py-1.5 text-muted">{featureLabel(k)}</td>
                  <td className="fig py-1.5 text-right text-dim">{(e.features[k] ?? 0).toFixed(3)}</td>
                  <td className="py-1.5">
                    <div className="flex items-center justify-end gap-2">
                      <span className="relative h-2 w-24">
                        <span className="absolute inset-y-0 left-1/2 w-px bg-border-strong" />
                        <span className="absolute inset-y-0 bg-accent/70" style={v > 0 ? { right: "50%", width: `${(Math.abs(v) / max) * 50}%` } : { left: "50%", width: `${(Math.abs(v) / max) * 50}%` }} />
                      </span>
                      <span className="fig w-12 text-right">{v > 0 ? "+" : v < 0 ? "−" : ""}{Math.abs(v).toFixed(3)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <dl className="grid content-start gap-y-1.5 text-[12px] sm:grid-cols-[130px_minmax(0,1fr)]">
        <dt className="text-dim">Prediction id</dt><dd className="mono break-all">{e.prediction_id}</dd>
        <dt className="text-dim">Inputs (SHA-256)</dt><dd className="mono break-all text-muted">{e.integrity.input_sha256}</dd>
        <dt className="text-dim">Model artifact</dt><dd className="mono break-all text-muted">{e.integrity.model_sha256}</dd>
        <dt className="text-dim">Code</dt><dd className="mono break-all text-muted">{e.integrity.code_sha256 ?? "—"} {e.integrity.code_matches_protocol ? <span className="text-pos">(matches the frozen protocol)</span> : <span className="text-warn">(differs from the frozen protocol)</span>}</dd>
        <dt className="text-dim">Ledger</dt><dd className="mono break-all text-muted">position {e.ledger_position}, chain hash {e.record_hash}</dd>
        {e.supersedes && <><dt className="text-dim">Supersedes</dt><dd className="mono break-all text-muted">{e.supersedes}</dd></>}
        <dt className="text-dim">Match page</dt><dd><Link href={`/matches/${e.match_uid}`} className="link">Open the match analysis</Link></dd>
      </dl>
    </div>
  );
}

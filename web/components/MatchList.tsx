"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { MatchSummary } from "@/lib/contract";
import { dayKey, familyName, favourite, NOT_RECORDED_SHORT, notRecorded, roundLabel, STATE_LABELS } from "@/lib/format";
import { groupByEdition } from "@/lib/matches";
import { LocalTime } from "./LocalTime";
import { ProbabilitySplit, Pct, TierBadge, tierOf } from "./match/parts";
import { Badge, EmptyState, SurfaceDot } from "./ui";

const UPCOMING = new Set(["scheduled", "in_progress", "postponed", "suspended"]);
const PENDING = new Set(["result_pending", "result_conflict"]);        // started, no final result yet
const RESULTS = new Set(["completed", "retired", "walkover", "cancelled"]);
const SHORT_REASON: Record<string, string> = {
  start_unconfirmed: "Forecast once a start time is set",
  identity_review: "Identity check in progress",
};
const TIER_ORDER = { slam: 0, premier: 1, tour: 2 } as const;

function useZone() {
  const [zone, setZone] = useState("UTC");
  useEffect(() => setZone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"), []);
  return zone;
}

/** One match: time and round, both players, and a single two-sided probability bar (or the stored reason for none). */
export function MatchRow({ m }: { m: MatchSummary }) {
  const ts = m.forecasts.tournament_start;
  const fav = ts.available ? favourite(ts.p) : null;
  const winner = m.result?.winner_index ?? null;
  const settled = m.result !== null;
  const names = [m.players[0].name ?? "To be decided", m.players[1].name ?? "To be decided"] as const;
  const lead = (i: number) => (!settled && fav === i) || winner === i;
  return (
    <Link href={`/matches/${m.uid}`}
          className="group grid grid-cols-[48px_minmax(0,1fr)_16px] items-center gap-x-4 gap-y-3 px-4 py-3.5 transition-colors hover:bg-card-hover focus-visible:bg-card-hover sm:grid-cols-[56px_minmax(0,1fr)_minmax(220px,300px)_16px] sm:px-5">
      <div className="text-[12px] leading-tight">
        <div className="fig text-text">{m.start ? <LocalTime iso={m.start} /> : "TBC"}</div>
        <div className="mt-1 text-dim" title={roundLabel(m.round)}>{m.round}</div>
      </div>

      <div className="grid min-w-0 gap-1">
        {names.map((n, i) => (
          <div key={i} className="flex min-w-0 items-center gap-2">
            <span className={`size-1.5 shrink-0 rounded-full ${lead(i) ? "bg-accent" : "bg-transparent"}`} aria-hidden="true" />
            <span className={`truncate text-[14px] ${lead(i) ? "font-medium text-text" : "text-text/75"}`}>{n}</span>
            {winner === i && <span className="text-[11px] text-pos">won</span>}
          </div>
        ))}
      </div>

      <div className="col-span-3 grid gap-1.5 sm:col-span-1 sm:col-start-3 sm:row-start-1">
        {settled && m.result?.score ? (
          <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-[12px]">
            <span className="fig text-muted">{m.result.score}</span>
            {ts.available && winner !== null && (fav === winner ? <Badge tone="pos">Favourite won</Badge> : <Badge tone="neg">Upset</Badge>)}
            {!ts.available && notRecorded(ts.reason_code) && <span className="basis-full text-right text-[11px] text-dim">{NOT_RECORDED_SHORT}</span>}
          </div>
        ) : ts.available ? (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <span className="flex items-baseline gap-1.5"><Pct value={ts.p[0]} fav={fav === 0} size="sm" /><span className="hidden text-[11px] text-dim lg:inline">{familyName(names[0])}</span></span>
              <span className="flex items-baseline gap-1.5"><span className="hidden text-[11px] text-dim lg:inline">{familyName(names[1])}</span><Pct value={ts.p[1]} fav={fav === 1} size="sm" /></span>
            </div>
            <ProbabilitySplit p={ts.p} height={6} />
          </>
        ) : (
          <span className="text-right text-[12px] text-dim">
            {notRecorded(ts.reason_code) ? NOT_RECORDED_SHORT : SHORT_REASON[ts.reason_code] ?? "No forecast"}
          </span>
        )}
        {!settled && (m.forecasts.round_aware.available || (m.state !== "scheduled" && m.state !== "time_tbc")) && (
          <div className="flex justify-end gap-1.5">
            {m.forecasts.round_aware.available && <Badge tone="accent">Round-aware update</Badge>}
            {m.state !== "scheduled" && m.state !== "time_tbc" && <Badge tone="warn">{STATE_LABELS[m.state]}</Badge>}
          </div>
        )}
      </div>

      <span className="sr-only">Open the match analysis</span>
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className="col-start-3 row-start-1 text-dim transition-transform group-hover:translate-x-0.5 group-hover:text-text sm:col-start-4">
        <path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </Link>
  );
}

export function TournamentGroup({ matches }: { matches: MatchSummary[] }) {
  const m0 = matches[0]!;
  const e = m0.edition;
  const tier = tierOf(e.level);
  const rounds = [...new Set(matches.map((m) => roundLabel(m.round)))].join(", ");
  return (
    <section aria-label={e.name} className={`overflow-hidden rounded-lg border bg-card ${tier === "slam" ? "border-accent/40" : "border-border"}`}>
      <header className={`flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border px-4 py-3 sm:px-5 ${tier === "slam" ? "shadow-[inset_3px_0_0_var(--color-accent)]" : ""}`}>
        <SurfaceDot surface={e.surface} />
        <h2 className={`text-[14px] ${tier === "tour" ? "font-medium" : "font-semibold"}`}>{e.name}</h2>
        <TierBadge tour={m0.tour} level={e.level} />
        <span className="text-[12px] text-dim">{e.surface ?? "Surface unknown"} · {rounds}</span>
        <span className="fig ml-auto text-[11px] text-dim">{matches.length} {matches.length === 1 ? "match" : "matches"}</span>
      </header>
      <ul className="divide-y divide-border">
        {matches.map((m) => <li key={m.uid}><MatchRow m={m} /></li>)}
      </ul>
    </section>
  );
}

type Tab = { key: string; label: React.ReactNode; count: number };
const seg = "rounded-[5px] px-2.5 py-1 text-[12px] transition-colors";
const segOn = "bg-card-hover text-text";
const segOff = "text-muted hover:text-text";

export function MatchList({ matches }: { matches: MatchSummary[] }) {
  const zone = useZone();
  const [tab, setTab] = useState<string | null>(null);
  const [tour, setTour] = useState<"All" | "ATP" | "WTA">("All");
  const [surface, setSurface] = useState<string>("All");
  const [majors, setMajors] = useState(false);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const t = q.get("tour");
    if (t === "ATP" || t === "WTA") setTour(t);
    if (q.get("day")) setTab(q.get("day"));
    if (q.get("surface")) setSurface(q.get("surface")!);
    if (q.get("majors") === "1") setMajors(true);
  }, []);

  const tabs = useMemo<Tab[]>(() => {
    const days = new Map<string, { iso: string; count: number }>();
    for (const m of matches) {
      if (!m.start || !UPCOMING.has(m.state)) continue;
      const key = dayKey(m.start, zone);
      const d = days.get(key) ?? { iso: m.start, count: 0 };
      d.count += 1;
      days.set(key, d);
    }
    const today = dayKey(new Date().toISOString(), zone);
    const tomorrow = dayKey(new Date(Date.now() + 86_400_000).toISOString(), zone);
    const list: Tab[] = [...days.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([key, d]) => ({
      key, count: d.count,
      label: key === today ? "Today" : key === tomorrow ? "Tomorrow"
        : new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: zone }).format(new Date(d.iso)),
    }));
    const tbc = matches.filter((m) => m.state === "time_tbc").length;
    if (tbc) list.push({ key: "tbc", label: "Time TBC", count: tbc });
    const pending = matches.filter((m) => PENDING.has(m.state)).length;
    if (pending) list.push({ key: "pending", label: "Results pending", count: pending });
    const results = matches.filter((m) => RESULTS.has(m.state)).length;
    if (results) list.push({ key: "results", label: "Results", count: results });
    return list;
  }, [matches, zone]);

  const active = tabs.find((t) => t.key === tab)?.key ?? tabs[0]?.key ?? "results";
  const surfaces = useMemo(() => [...new Set(matches.map((m) => m.edition.surface).filter((s): s is string => Boolean(s)))].sort(), [matches]);

  useEffect(() => {
    const q = new URLSearchParams();
    if (tab) q.set("day", tab);
    if (tour !== "All") q.set("tour", tour);
    if (surface !== "All") q.set("surface", surface);
    if (majors) q.set("majors", "1");
    window.history.replaceState(null, "", q.toString() ? `?${q}` : window.location.pathname);
  }, [tab, tour, surface, majors]);

  const shown = matches.filter((m) => {
    if (tour !== "All" && m.tour !== tour) return false;
    if (surface !== "All" && m.edition.surface !== surface) return false;
    if (majors && tierOf(m.edition.level) === "tour") return false;
    if (active === "tbc") return m.state === "time_tbc";
    if (active === "pending") return PENDING.has(m.state);
    if (active === "results") return RESULTS.has(m.state);
    return Boolean(m.start) && UPCOMING.has(m.state) && dayKey(m.start!, zone) === active;
  });
  const groups = groupByEdition(shown).sort((a, b) => TIER_ORDER[tierOf(a[0]!.edition.level)] - TIER_ORDER[tierOf(b[0]!.edition.level)]);
  const filtered = tour !== "All" || surface !== "All" || majors;

  return (
    <div className="grid gap-5">
      <div className="grid gap-3 rounded-lg border border-border bg-card/50 p-3">
        <div role="tablist" aria-label="Day" className="flex gap-1 overflow-x-auto">
          {tabs.map((t) => (
            <button key={t.key} role="tab" aria-selected={t.key === active} onClick={() => setTab(t.key)}
                    className={`whitespace-nowrap rounded-md border px-3 py-1.5 text-[13px] transition-colors ${t.key === active ? "border-border-strong bg-card-hover text-text" : "border-transparent text-muted hover:text-text"}`}>
              {t.label} <span className="fig ml-1 text-[11px] text-dim">{t.count}</span>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px]">
          <span role="group" aria-label="Tour" className="inline-flex gap-0.5 rounded-md border border-border bg-bg p-0.5">
            {(["All", "ATP", "WTA"] as const).map((t) => (
              <button key={t} aria-pressed={tour === t} onClick={() => setTour(t)} className={`${seg} ${tour === t ? segOn : segOff}`}>{t === "All" ? "All tours" : t}</button>
            ))}
          </span>
          {surfaces.length > 1 && (
            <span role="group" aria-label="Surface" className="inline-flex gap-0.5 rounded-md border border-border bg-bg p-0.5">
              {["All", ...surfaces].map((s) => (
                <button key={s} aria-pressed={surface === s} onClick={() => setSurface(s)} className={`${seg} inline-flex items-center gap-1.5 ${surface === s ? segOn : segOff}`}>
                  {s !== "All" && <SurfaceDot surface={s} />}{s === "All" ? "All surfaces" : s}
                </button>
              ))}
            </span>
          )}
          <button aria-pressed={majors} onClick={() => setMajors((v) => !v)} className={`rounded-md border px-2.5 py-1 transition-colors ${majors ? "border-accent/50 bg-accent-soft text-accent" : "border-border text-muted hover:text-text"}`}>
            Majors and 1000s only
          </button>
          <span className="ml-auto flex items-center gap-3 text-dim" aria-live="polite">
            <span className="fig">{shown.length} {shown.length === 1 ? "match" : "matches"}</span>
            {filtered && <button type="button" onClick={() => { setTour("All"); setSurface("All"); setMajors(false); }} className="link">Reset</button>}
          </span>
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="card"><EmptyState title="No matches here">Try another day, or reset the filters.</EmptyState></div>
      ) : (
        groups.map((g) => <TournamentGroup key={g[0]!.edition.uid} matches={g} />)
      )}
      <p className="text-[12px] text-dim">
        {active === "tbc" ? "Forecasts are issued once a start time is published, at least 30 minutes before play."
          : active === "pending" ? "These matches have started. Each keeps its pre-match forecast; the final result appears here shortly after the match ends."
          : `Times in ${zone}. Percentages are the tournament-start forecast; open a match for the round-aware update and the reasoning.`}
      </p>
    </div>
  );
}

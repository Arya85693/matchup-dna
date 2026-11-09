"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { MatchSummary } from "@/lib/contract";
import { dayKey, favourite, levelLabel, STATE_LABELS } from "@/lib/format";
import { groupByEdition } from "@/lib/matches";
import { LocalTime } from "./LocalTime";
import { Badge, EmptyState, SurfaceDot } from "./ui";
import { IconChevron } from "./icons";

const UPCOMING = new Set(["scheduled", "in_progress", "postponed", "suspended"]);
const RESULTS = new Set(["completed", "retired", "walkover", "cancelled", "result_pending", "result_conflict"]);
const SHORT_REASON: Record<string, string> = {
  start_unconfirmed: "Awaiting start time",
  too_late_in_progress: "Not forecast",
  too_late_played: "Not forecast",
  too_late: "Not forecast",
  identity_review: "Identity check",
};

function useZone() {
  const [zone, setZone] = useState("UTC");
  useEffect(() => setZone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"), []);
  return zone;
}

/** One match as two player lines (Sofascore-style), each with its stored probability and a small share bar. */
export function MatchRow({ m }: { m: MatchSummary }) {
  const ts = m.forecasts.tournament_start;
  const fav = ts.available ? favourite(ts.p) : null;
  const winner = m.result?.winner_index ?? null;
  const settled = m.result !== null;
  return (
    <Link href={`/matches/${m.uid}`}
          className="group grid grid-cols-[52px_minmax(0,1fr)_auto_16px] items-center gap-x-4 px-5 py-3.5 transition-colors hover:bg-card-hover">
      <div className="text-[12px] leading-tight text-muted">
        <div className="num text-text">{m.start ? <LocalTime iso={m.start} /> : "TBC"}</div>
        <div className="mt-0.5">{m.round}</div>
      </div>
      <div className="grid min-w-0 gap-1.5">
        {m.players.map((p, i) => (
          <div key={i} className="flex min-w-0 items-baseline gap-2">
            <span className={`truncate ${winner === i || (!settled && fav === i) ? "font-medium text-text" : "text-text/80"}`}>{p.name ?? "To be decided"}</span>
            {p.rank !== null && <span className="num text-[12px] text-dim">{p.rank}</span>}
            {winner === i && <span className="text-[11px] text-pos" aria-label="winner">●</span>}
          </div>
        ))}
      </div>
      <div className="grid justify-items-end gap-1.5">
        {settled && m.result?.score ? (
          <span className="num text-[12px] text-muted">{m.result.score}</span>
        ) : ts.available ? (
          ts.p.map((v, i) => (
            <div key={i} className="flex items-center gap-2.5">
              <span className="hidden h-1 w-14 overflow-hidden rounded-full bg-track sm:block" aria-hidden="true">
                <span className={`block h-full ${fav === i ? "bg-accent" : "bg-dim/50"}`} style={{ width: `${v * 100}%` }} />
              </span>
              <span className={`num w-12 text-right ${fav === i ? "font-semibold text-text" : "text-muted"}`}>{(v * 100).toFixed(1)}%</span>
            </div>
          ))
        ) : (
          <span className="text-[12px] text-dim">{SHORT_REASON[ts.reason_code] ?? "No forecast"}</span>
        )}
        {!settled && m.state !== "scheduled" && m.state !== "time_tbc" && <Badge tone="warn">{STATE_LABELS[m.state]}</Badge>}
      </div>
      <IconChevron className="text-dim transition-colors group-hover:text-text" />
    </Link>
  );
}

export function TournamentGroup({ matches }: { matches: MatchSummary[] }) {
  const e = matches[0]!.edition;
  return (
    <section className="card overflow-hidden" aria-label={e.name}>
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-card px-5 py-3">
        <SurfaceDot surface={e.surface} />
        <h3 className="text-[13px] font-medium">{e.name}</h3>
        <span className="text-[12px] text-dim">{levelLabel(matches[0]!.tour, e.level)} · {e.surface ?? "Surface unknown"}</span>
      </header>
      <ul className="divide-y divide-border">
        {matches.map((m) => <li key={m.uid}><MatchRow m={m} /></li>)}
      </ul>
    </section>
  );
}

type Tab = { key: string; label: React.ReactNode; count: number };

export function MatchList({ matches }: { matches: MatchSummary[] }) {
  const zone = useZone();
  const [tab, setTab] = useState<string | null>(null);
  const [tour, setTour] = useState<"All" | "ATP" | "WTA">("All");

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const t = q.get("tour");
    if (t === "ATP" || t === "WTA") setTour(t);
    if (q.get("day")) setTab(q.get("day"));
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
    const results = matches.filter((m) => RESULTS.has(m.state)).length;
    if (results) list.push({ key: "results", label: "Results", count: results });
    return list;
  }, [matches, zone]);

  const active = tabs.find((t) => t.key === tab)?.key ?? tabs[0]?.key ?? "results";

  useEffect(() => {
    const q = new URLSearchParams();
    if (tab) q.set("day", tab);
    if (tour !== "All") q.set("tour", tour);
    window.history.replaceState(null, "", q.toString() ? `?${q}` : window.location.pathname);
  }, [tab, tour]);

  const shown = matches.filter((m) => {
    if (tour !== "All" && m.tour !== tour) return false;
    if (active === "tbc") return m.state === "time_tbc";
    if (active === "results") return RESULTS.has(m.state);
    return Boolean(m.start) && UPCOMING.has(m.state) && dayKey(m.start!, zone) === active;
  });

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Day" className="flex flex-wrap gap-1 rounded-lg border border-border bg-card p-1">
          {tabs.map((t) => (
            <button key={t.key} role="tab" aria-selected={t.key === active} onClick={() => setTab(t.key)}
                    className={`rounded-md px-3 py-1.5 text-[13px] transition-colors ${t.key === active ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>
              {t.label} <span className="num ml-1 text-dim">{t.count}</span>
            </button>
          ))}
        </div>
        <div role="group" aria-label="Tour" className="flex gap-1 rounded-lg border border-border bg-card p-1">
          {(["All", "ATP", "WTA"] as const).map((t) => (
            <button key={t} aria-pressed={tour === t} onClick={() => setTour(t)}
                    className={`rounded-md px-3 py-1.5 text-[13px] ${tour === t ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>
              {t === "All" ? "All tours" : t}
            </button>
          ))}
        </div>
      </div>
      {shown.length === 0 ? (
        <div className="card"><EmptyState title="No matches here">Try another day or both tours.</EmptyState></div>
      ) : (
        groupByEdition(shown).map((g) => <TournamentGroup key={g[0]!.edition.uid} matches={g} />)
      )}
      <p className="text-[12px] text-dim">
        {active === "tbc" ? "Forecasts are issued once a start time is published, at least 30 minutes before play." : `Times in ${zone}.`}
      </p>
    </div>
  );
}


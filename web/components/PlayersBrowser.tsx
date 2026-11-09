"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { HistoryListing } from "@/lib/contract";
import { Spark } from "./EloChart";
import { EmptyState, SurfaceDot } from "./ui";

type SortKey = "elo" | "rank" | "Hard" | "Clay" | "Grass" | "form" | "season";
const PAGE = 50;

export function PlayersBrowser({ players }: { players: HistoryListing[] }) {
  const [tour, setTour] = useState<"ATP" | "WTA">("ATP");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("elo");
  const [limit, setLimit] = useState(PAGE);

  const rows = useMemo(() => {
    const query = q.trim().toLowerCase();
    const list = players.filter((p) => p.tour === tour && (!query || p.name.toLowerCase().includes(query)));
    const key = (p: HistoryListing): number => {
      if (sort === "rank") return p.rank ?? 100_000;
      if (sort === "form") return -(p.elo_change_90d ?? -1e9);
      if (sort === "season") return -(p.season[0] / Math.max(1, p.season[0] + p.season[1])) - p.season[0] / 1e4;
      if (sort === "elo") return -p.elo;
      return -p.surfaces[sort];
    };
    return list.sort((a, b) => key(a) - key(b));
  }, [players, tour, q, sort]);

  const header = (label: string, key: SortKey, align = "text-right") => (
    <th className={`px-3 py-3 font-normal ${align}`}>
      <button onClick={() => setSort(key)} aria-pressed={sort === key} className={`${sort === key ? "text-accent" : "hover:text-text"}`}>{label}{sort === key ? " ↓" : ""}</button>
    </th>
  );

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Tour" className="flex gap-1 rounded-lg border border-border bg-card p-1">
          {(["ATP", "WTA"] as const).map((t) => (
            <button key={t} aria-pressed={tour === t} onClick={() => { setTour(t); setLimit(PAGE); }}
                    className={`rounded-md px-4 py-1.5 text-[13px] ${tour === t ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>{t}</button>
          ))}
        </div>
        <label className="relative min-w-[220px] flex-1 sm:max-w-[320px]">
          <span className="sr-only">Search players</span>
          <input id="player-search" value={q} onChange={(e) => { setQ(e.target.value); setLimit(PAGE); }} placeholder={`Search ${players.filter((p) => p.tour === tour).length} ${tour} players`}
                 className="w-full rounded-lg border border-border bg-card px-3 py-2 text-[13px] outline-none placeholder:text-dim focus:border-accent" />
        </label>
      </div>

      <div className="card overflow-x-auto" tabIndex={0} role="region" aria-label="Players">
        {rows.length === 0 ? <EmptyState title="No players match" /> : (
          <table className="w-full min-w-[760px] text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-[12px] text-dim">
                <th className="w-12 px-5 py-3 font-normal">#</th>
                <th className="px-3 py-3 font-normal">Player</th>
                {header("Elo", "elo")}
                {header("Rank", "rank")}
                {(["Hard", "Clay", "Grass"] as const).map((s) => (
                  <th key={s} className="px-3 py-3 text-right font-normal">
                    <button onClick={() => setSort(s)} aria-pressed={sort === s} className={`inline-flex items-center gap-1.5 ${sort === s ? "text-accent" : "hover:text-text"}`}><SurfaceDot surface={s} />{s}</button>
                  </th>
                ))}
                {header("Season", "season")}
                {header("90 days", "form")}
                <th className="px-5 py-3 text-right font-normal">Trend</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.slice(0, limit).map((p, i) => (
                <tr key={p.id} className="hover:bg-card-hover">
                  <td className="num px-5 py-2.5 text-dim">{i + 1}</td>
                  <td className="px-3 py-2.5"><Link href={`/players/${p.id}`} className="font-medium hover:text-accent">{p.name}</Link></td>
                  <td className="num px-3 py-2.5 text-right font-medium">{Math.round(p.elo)}</td>
                  <td className="num px-3 py-2.5 text-right text-muted">{p.rank ?? "—"}</td>
                  {(["Hard", "Clay", "Grass"] as const).map((s) => <td key={s} className="num px-3 py-2.5 text-right text-muted">{Math.round(p.surfaces[s])}</td>)}
                  <td className="num px-3 py-2.5 text-right text-muted">{p.season[0]}–{p.season[1]}</td>
                  <td className={`num px-3 py-2.5 text-right ${p.elo_change_90d === null ? "text-dim" : p.elo_change_90d >= 0 ? "text-pos" : "text-neg"}`}>
                    {p.elo_change_90d === null ? "—" : `${p.elo_change_90d >= 0 ? "+" : ""}${Math.round(p.elo_change_90d)}`}
                  </td>
                  <td className="px-5 py-2.5 text-right"><Spark values={p.spark} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {rows.length > limit && (
        <button onClick={() => setLimit((l) => l + PAGE)} className="mx-auto rounded-lg border border-border bg-card px-4 py-2 text-[13px] text-muted hover:text-text">
          Show more ({rows.length - limit} left)
        </button>
      )}
    </div>
  );
}

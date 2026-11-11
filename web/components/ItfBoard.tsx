"use client";

import { useMemo, useState } from "react";
import type { ItfBoardRowT, ItfBoardT } from "@/lib/contract";
import { Segmented } from "./lab/parts";
import { EmptyState } from "./ui";

const PAGE = 50;

function day(yyyymmdd: number) {
  const s = String(yyyymmdd);
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
}

/** The ITF players board: active ITF players by the ITF rating (display only, not a forecast). */
export function ItfBoard({ board }: { board: ItfBoardT }) {
  const [tour, setTour] = useState<"ATP" | "WTA">("ATP");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);
  const rows: ItfBoardRowT[] = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all = board.tours[tour];
    return q ? all.filter((r) => r.name.toLowerCase().includes(q) || (r.country ?? "").toLowerCase().includes(q)) : all;
  }, [board, tour, query]);
  const rankList = board.rank_lists[tour];
  return (
    <section className="card" aria-label="ITF players">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3.5">
        <Segmented label="Tour" value={tour} onChange={(v) => { setTour(v); setShown(PAGE); }}
                   options={[["ATP", "Men"], ["WTA", "Women"]]} />
        <input type="search" value={query} onChange={(e) => { setQuery(e.target.value); setShown(PAGE); }}
               placeholder="Search players or country" aria-label="Search ITF players"
               className="w-full max-w-[16rem] rounded-md border border-border bg-bg px-3 py-1.5 text-[13px]" />
      </div>
      {rows.length === 0 ? <EmptyState title="No players match">Try another name or country.</EmptyState> : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="text-dim">
              <tr>
                <th scope="col" className="px-5 py-2.5 font-normal">#</th>
                <th scope="col" className="py-2.5 font-normal">Player</th>
                <th scope="col" className="py-2.5 font-normal">Country</th>
                <th scope="col" className="py-2.5 text-right font-normal">ITF rating</th>
                <th scope="col" className="py-2.5 text-right font-normal">{tour === "ATP" ? "ATP" : "WTA"} rank</th>
                <th scope="col" className="py-2.5 text-right font-normal">ITF record, 52 weeks</th>
                <th scope="col" className="px-5 py-2.5 text-right font-normal">Last ITF event</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.slice(0, shown).map((r) => (
                <tr key={r.id}>
                  <td className="num px-5 py-3 text-dim">{r.position}</td>
                  <td className="py-3 font-medium">{r.name}</td>
                  <td className="py-3 text-muted">{r.country ?? "–"}</td>
                  <td className="num py-3 text-right">{Math.round(r.rating)}</td>
                  <td className="num py-3 text-right text-muted">{r.rank ?? "–"}</td>
                  <td className="num py-3 text-right text-muted">{r.wins}–{r.losses}</td>
                  <td className="num px-5 py-3 text-right text-dim">{day(r.last_event)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3.5 text-[12px] text-dim">
        <span>
          {rows.length.toLocaleString()} players with at least {board.min_matches} ITF main-draw matches in 52 weeks
          {rankList ? ` · ranks from the ${rankList} list` : ""}
        </span>
        {shown < rows.length && (
          <button type="button" onClick={() => setShown((n) => n + PAGE)} className="link">Show {Math.min(PAGE, rows.length - shown)} more</button>
        )}
      </div>
    </section>
  );
}

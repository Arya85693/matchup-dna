"use client";

import { useState } from "react";
import type { HistoryPlayer } from "@/lib/contract";
import { familyName, roundLabel } from "@/lib/format";
import { SurfaceDot } from "../ui";

const SURFACES = ["Hard", "Clay", "Grass"] as const;
const SHOWN = 6;

/** Career meetings between two players on the same tour, from A's side (B's record mirrors it). `allLevels`: the ITF
 * board's history counts matches at every level, not only tour-level ones. */
export function HeadToHead({ a, b, allLevels = false }: { a: HistoryPlayer; b: HistoryPlayer; allLevels?: boolean }) {
  const level = allLevels ? "" : "tour-level ";
  const [all, setAll] = useState(false);
  const meetings = a.h2h[String(b.id)] ?? [];
  const aWins = meetings.filter((m) => m.won).length;
  const bWins = meetings.length - aWins;

  if (meetings.length === 0) {
    return (
      <section aria-label="Head to head" className="rounded-xl border border-border bg-card px-5 py-6 text-center">
        <h2 className="text-[13px] text-muted">Head to head</h2>
        <p className="mt-2 text-[20px] font-semibold">Never played before</p>
        <p className="mt-1 text-[13px] text-dim">{a.name} and {b.name} have not met in a completed {level}match.</p>
      </section>
    );
  }

  const leader = aWins === bWins ? null : aWins > bWins ? a : b;
  const bySurface = SURFACES.map((s) => {
    const on = meetings.filter((m) => m.surface === s);
    return { s, a: on.filter((m) => m.won).length, b: on.filter((m) => !m.won).length };
  }).filter((x) => x.a + x.b > 0);
  const shown = all ? meetings : meetings.slice(0, SHOWN);

  return (
    <section aria-label="Head to head" className="rounded-xl border border-border bg-card">
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-4 px-5 pb-4 pt-5">
        <p className={`fig text-left text-[40px] font-semibold leading-none ${aWins >= bWins ? "text-text" : "text-muted"}`}>{aWins}</p>
        <div className="text-center">
          <h2 className="text-[13px] font-medium">Head to head</h2>
          <p className="mt-1 text-[12px] text-dim">
            {meetings.length} meeting{meetings.length === 1 ? "" : "s"} · {leader ? `${familyName(leader.name)} leads` : "level"}
          </p>
        </div>
        <p className={`fig text-right text-[40px] font-semibold leading-none ${bWins >= aWins ? "text-text" : "text-muted"}`}>{bWins}</p>
      </div>
      <div className="mx-5 flex h-2 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
        {aWins > 0 && <span className={`anim-fill h-full ${aWins >= bWins ? "bg-accent" : "bg-underdog"}`} style={{ width: `${(aWins / meetings.length) * 100}%`, transformOrigin: "left" }} />}
        {bWins > 0 && <span className={`anim-fill h-full ${bWins >= aWins ? "bg-accent" : "bg-underdog"}`} style={{ width: `${(bWins / meetings.length) * 100}%`, transformOrigin: "right" }} />}
      </div>
      {bySurface.length > 0 && (
        <ul className="flex flex-wrap justify-center gap-x-5 gap-y-1 px-5 pt-3 text-[12px] text-muted" aria-label="By surface">
          {bySurface.map((x) => (
            <li key={x.s} className="inline-flex items-center gap-1.5"><SurfaceDot surface={x.s} />{x.s} <span className="fig text-text">{x.a}–{x.b}</span></li>
          ))}
        </ul>
      )}
      <ul className="mt-4 divide-y divide-border border-t border-border">
        {shown.map((m, i) => {
          const winner = m.won ? a : b;
          return (
            <li key={i} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-5 py-2.5 text-[13px]">
              <span className="min-w-0">
                <span className="block truncate">{m.event || "Tournament"} <span className="text-dim">· {roundLabel(m.round)}</span></span>
                <span className="flex items-center gap-1.5 text-[11px] text-dim">{m.surface && <SurfaceDot surface={m.surface} />}{m.surface ?? "Surface unknown"} · {m.date}</span>
              </span>
              <span className="text-right text-[12px]">
                <span className={m.won ? "text-text" : "text-muted"}>{familyName(winner.name)} won</span>
                {m.retired && <span className="ml-1.5 text-dim">(retired)</span>}
              </span>
            </li>
          );
        })}
      </ul>
      {meetings.length > SHOWN && (
        <div className="border-t border-border px-5 py-2.5 text-center">
          <button type="button" onClick={() => setAll((v) => !v)} className="text-[12px] text-muted hover:text-text">
            {all ? "Show fewer" : `Show all ${meetings.length} meetings`}
          </button>
        </div>
      )}
      <p className="border-t border-border px-5 py-2.5 text-[11px] text-dim">Completed and retired {level}matches in the match history{allLevels ? ", at every level" : ""}; walkovers are not counted.</p>
    </section>
  );
}

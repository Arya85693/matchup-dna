"use client";

import Link from "next/link";
import { useState } from "react";
import type { ArchiveEntry } from "@/lib/contract";
import { favourite, pct } from "@/lib/format";
import { LocalTime } from "./LocalTime";
import { Badge, EmptyState } from "./ui";

type Filter = "all" | "tournament_start" | "round_aware";
type Outcome = "all" | "settled" | "pending";

export function ArchiveTable({ entries }: { entries: ArchiveEntry[] }) {
  const [model, setModel] = useState<Filter>("all");
  const [outcome, setOutcome] = useState<Outcome>("all");
  const shown = entries.filter((e) => (model === "all" || e.kind === model)
    && (outcome === "all" || (outcome === "settled" ? e.result_status !== null : e.result_status === null)));
  const seg = <T extends string>(value: T, set: (v: T) => void, options: [T, string][], label: string) => (
    <div role="group" aria-label={label} className="flex gap-1 rounded-lg border border-border bg-card p-1">
      {options.map(([v, l]) => (
        <button key={v} aria-pressed={value === v} onClick={() => set(v)} className={`rounded-md px-3 py-1.5 text-[13px] ${value === v ? "bg-card-hover text-text" : "text-muted hover:text-text"}`}>{l}</button>
      ))}
    </div>
  );
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap gap-3">
        {seg(model, setModel, [["all", "All models"], ["tournament_start", "Tournament start"], ["round_aware", "Round-aware"]], "Model")}
        {seg(outcome, setOutcome, [["all", "All"], ["settled", "Settled"], ["pending", "Pending"]], "Outcome")}
      </div>
      <div className="card overflow-x-auto" tabIndex={0} role="region" aria-label="Forecast archive">
        {shown.length === 0 ? <EmptyState title="No forecasts match these filters" /> : (
          <table className="w-full min-w-[820px] text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-[12px] text-dim">
                <th className="px-5 py-3 font-normal">Issued</th>
                <th className="px-3 py-3 font-normal">Match</th>
                <th className="px-3 py-3 font-normal">Favourite</th>
                <th className="px-3 py-3 font-normal">Model</th>
                <th className="px-3 py-3 font-normal">Status</th>
                <th className="px-3 py-3 font-normal">Outcome</th>
                <th className="px-5 py-3 font-normal">Ledger</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {shown.map((e) => {
                const fav = favourite(e.p);
                return (
                  <tr key={e.prediction_id} className="hover:bg-card-hover">
                    <td className="num whitespace-nowrap px-5 py-3 text-muted"><LocalTime iso={e.issued_at} style="datetime" /></td>
                    <td className="px-3 py-3">
                      <Link href={`/matches/${e.match_uid}`} className="hover:text-accent">{e.players[0]} v {e.players[1]}</Link>
                      <p className="text-[12px] text-dim">{e.event} · {e.round}</p>
                    </td>
                    <td className="num px-3 py-3">{fav !== null ? `${e.players[fav]?.split(" ").slice(-1)[0]} ${pct(e.p[fav])}%` : "50 / 50"}</td>
                    <td className="mono px-3 py-3 text-muted">{e.model_version}</td>
                    <td className="px-3 py-3">{e.counted ? <Badge tone="accent">Scored</Badge> : e.superseded ? <Badge>Superseded</Badge> : <Badge>Not counted</Badge>}</td>
                    <td className="px-3 py-3">
                      {e.favourite_won === true ? <Badge tone="pos">Favourite won</Badge>
                        : e.favourite_won === false ? <Badge tone="neg">Upset</Badge>
                        : e.result_status ? <Badge>{e.result_status}</Badge> : <span className="text-[12px] text-dim">Pending</span>}
                    </td>
                    <td className="mono px-5 py-3 text-dim" title={e.record_hash}>#{e.ledger_position} · {e.record_hash.slice(0, 8)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <p className="text-[12px] text-dim">Forecasts cannot be edited or deleted. Each one&apos;s hash covers the one before it, so any change would break the chain. The ledger file is committed to the public repository.</p>
    </div>
  );
}

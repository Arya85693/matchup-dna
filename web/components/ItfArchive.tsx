"use client";

import { useMemo, useState } from "react";
import type { ItfArchiveRowT } from "@/lib/contract";
import { circuitLabel, pct, roundLabel } from "@/lib/format";
import { Segmented } from "./lab/parts";
import { LocalTime } from "./LocalTime";
import { Badge, EmptyState } from "./ui";

const PAGE = 50;
const STATUS: Record<ItfArchiveRowT["status"], { label: string; tone: "accent" | "neutral" | "warn" }> = {
  counted: { label: "Counted (first issued)", tone: "accent" },
  pilot: { label: "Pilot (before P2)", tone: "warn" },
  revision: { label: "Later revision", tone: "neutral" },
};

/** Every ITF forecast (model ITF M1), locked before its match, with its prediction id and chain hash. */
export function ItfArchive({ rows }: { rows: ItfArchiveRowT[] }) {
  const [q, setQ] = useState("");
  const [tour, setTour] = useState<"all" | "ATP" | "WTA">("all");
  const [shown, setShown] = useState(PAGE);
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return rows.filter((r) => (tour === "all" || r.tour === tour)
      && (!s || [r.a, r.b, r.event].some((x) => (x ?? "").toLowerCase().includes(s))));
  }, [rows, q, tour]);
  if (!rows.length) return <div className="card"><EmptyState title="No ITF forecasts yet">They appear here from the first live ITF run.</EmptyState></div>;
  return (
    <section className="card" aria-label="ITF forecasts">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3.5">
        <Segmented label="Circuit" value={tour} onChange={(v) => { setTour(v); setShown(PAGE); }}
                   options={[["all", "All ITF"], ["ATP", "ITF Men"], ["WTA", "ITF Women"]]} />
        <input type="search" value={q} onChange={(e) => { setQ(e.target.value); setShown(PAGE); }}
               placeholder="Search players or event" aria-label="Search ITF forecasts"
               className="w-full max-w-[16rem] rounded-md border border-border bg-bg px-3 py-1.5 text-[13px]" />
      </div>
      <ul className="divide-y divide-border">
        {filtered.slice(0, shown).map((r) => {
          const st = STATUS[r.status];
          return (
            <li key={r.prediction_id} className="grid gap-3 px-5 py-4 lg:grid-cols-[13rem_1fr_9rem_11rem] lg:items-center">
              <div className="text-[13px] text-muted">
                Issued <LocalTime iso={r.issued_at} style="datetime" />
                <p className="mt-1 text-[12px] text-dim"><span className="text-muted">{circuitLabel(r.tour, null, "itf")}</span> · {r.event} · {roundLabel(r.round)}</p>
              </div>
              <div className="grid gap-1">
                <span className={r.p_a >= 0.5 ? "font-medium" : "text-muted"}>{r.a} <span className="num text-dim">{pct(r.p_a)}%</span>{r.winner === "a" && <span className="ml-1.5 text-pos">✓</span>}</span>
                <span className={r.p_a < 0.5 ? "font-medium" : "text-muted"}>{r.b} <span className="num text-dim">{pct(1 - r.p_a)}%</span>{r.winner === "b" && <span className="ml-1.5 text-pos">✓</span>}</span>
              </div>
              <div className="grid gap-1 text-[12px] text-dim">
                <span>Elo only {r.p_a_elo === null ? "–" : `${pct(r.p_a_elo)}%`}</span>
                <span>{r.result ? (r.result === "completed" ? "Result recorded" : r.result) : "Awaiting result"}</span>
              </div>
              <div className="grid gap-1.5 lg:justify-items-end">
                <Badge tone={st.tone}>{st.label}</Badge>
                <span className="mono text-[11px] text-dim" title={`prediction ${r.prediction_id}, chain hash ${r.record_hash}`}>#{r.seq} · {r.record_hash.slice(0, 12)}</span>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3.5 text-[12px] text-dim">
        <span>{filtered.length.toLocaleString()} ITF forecasts · model ITF M1, the Elo-only forecast beside it</span>
        {shown < filtered.length && <button type="button" onClick={() => setShown((n) => n + PAGE)} className="link">Show {Math.min(PAGE, filtered.length - shown)} more</button>}
      </div>
    </section>
  );
}

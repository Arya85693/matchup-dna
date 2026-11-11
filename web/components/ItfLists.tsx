/** ITF match rows, shared by the ITF page and the Matches page. Stored probabilities only; nothing is computed. */
import type { ItfEntryT, ItfRecentT } from "@/lib/contract";
import { circuitLabel, pct, roundLabel } from "@/lib/format";
import { LocalTime } from "./LocalTime";
import { EmptyState } from "./ui";

function Players({ e }: { e: ItfEntryT | ItfRecentT }) {
  const aFav = e.p_a >= 0.5;
  const winner = "winner" in e ? e.winner : null;
  return (
    <div className="grid gap-1">
      <span className={aFav ? "font-medium" : "text-muted"}>
        {e.a ?? "Player A"} <span className="num text-dim">{pct(e.p_a)}%</span>{winner === "a" && <span className="ml-1.5 text-pos">✓</span>}
      </span>
      <span className={!aFav ? "font-medium" : "text-muted"}>
        {e.b ?? "Player B"} <span className="num text-dim">{pct(1 - e.p_a)}%</span>{winner === "b" && <span className="ml-1.5 text-pos">✓</span>}
      </span>
    </div>
  );
}

function When({ e }: { e: ItfEntryT }) {
  return (
    <div className="text-[13px] text-muted">
      {e.start ? <LocalTime iso={e.start} style="datetime" /> : "Time to be set"}
      <p className="mt-1 text-[12px] text-dim">
        <span className="text-muted">{circuitLabel(e.tour, null, "itf")}</span> · {e.event} · {roundLabel(e.round)}
      </p>
    </div>
  );
}

export function ItfUpcoming({ rows, limit = 80 }: { rows: ItfEntryT[]; limit?: number }) {
  if (!rows.length) return <EmptyState title="No upcoming ITF forecasts">Forecasts appear here once the next order of play is published.</EmptyState>;
  return (
    <ul className="divide-y divide-border">
      {rows.slice(0, limit).map((e) => (
        <li key={e.uid} className="grid gap-3 px-5 py-4 sm:grid-cols-[13rem_1fr_6rem] sm:items-center">
          <When e={e} />
          <Players e={e} />
          <p className="num text-[12px] text-dim sm:text-right" title="Elo-only forecast for the first-named player">
            Elo {e.p_a_elo === null ? "–" : `${pct(e.p_a_elo)}%`}
          </p>
        </li>
      ))}
    </ul>
  );
}

export function ItfRecent({ rows, limit = 40 }: { rows: ItfRecentT[]; limit?: number }) {
  if (!rows.length) return <EmptyState title="No settled ITF forecasts yet">Results appear here as matches finish.</EmptyState>;
  return (
    <ul className="divide-y divide-border">
      {rows.slice(0, limit).map((e) => (
        <li key={e.uid} className="grid gap-3 px-5 py-4 sm:grid-cols-[13rem_1fr_8rem] sm:items-center">
          <When e={e} />
          <Players e={e} />
          <p className="num text-[12px] text-dim sm:text-right">{e.status === "completed" ? e.score : e.status}</p>
        </li>
      ))}
    </ul>
  );
}

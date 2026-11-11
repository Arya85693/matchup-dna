"use client";

import { useId, useMemo, useRef, useState } from "react";
import { PlayerPhoto } from "../PlayerPhoto";

export type PickOption = { id: number; name: string; tour: "ATP" | "WTA"; photo: string | null; elo_rank: number };

/** Search any player by name (combobox pattern: type, arrow keys to move, Enter to choose, Esc to close). */
export function PlayerPicker({ options, value, onPick, label, exclude, tourName = (t) => t }: {
  options: PickOption[]; value: PickOption | null; onPick: (id: number) => void; label: string; exclude?: number | null;
  tourName?: (tour: PickOption["tour"]) => string;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const results = useMemo(() => {
    const query = q.trim().toLowerCase();
    const pool = options.filter((o) => o.id !== exclude);
    const hits = query ? pool.filter((o) => o.name.toLowerCase().includes(query)) : pool.filter((o) => o.elo_rank <= 5);
    return hits.sort((a, b) => a.elo_rank - b.elo_rank || a.name.localeCompare(b.name)).slice(0, 8);
  }, [options, q, exclude]);
  const choose = (o: PickOption) => { onPick(o.id); setQ(""); setOpen(false); input.current?.blur(); };

  return (
    <div className="relative">
      <label htmlFor={`${id}-input`} className="sr-only">{label}</label>
      <div className="flex items-center gap-2 rounded-lg border border-border bg-bg px-3 py-2 focus-within:border-accent">
        <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" className="shrink-0 text-dim"><circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="m10.5 10.5 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
        <input ref={input} id={`${id}-input`} role="combobox" aria-expanded={open} aria-controls={`${id}-list`} aria-autocomplete="list"
               aria-activedescendant={open && results[active] ? `${id}-opt-${results[active]!.id}` : undefined}
               value={q} placeholder={value ? `Change ${value.name}` : "Search a player"} autoComplete="off"
               onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(0); }}
               onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 120)}
               onKeyDown={(e) => {
                 if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(results.length - 1, a + 1)); }
                 if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
                 if (e.key === "Enter" && results[active]) { e.preventDefault(); choose(results[active]!); }
                 if (e.key === "Escape") { setOpen(false); setQ(""); }
               }}
               className="w-full bg-transparent text-[13px] outline-none placeholder:text-dim" />
      </div>
      {open && (
        <ul id={`${id}-list`} role="listbox" aria-label={label}
            className="absolute inset-x-0 top-full z-30 mt-1 max-h-[320px] overflow-auto rounded-lg border border-border-strong bg-bg py-1 shadow-xl">
          {!q && <li className="px-3 py-1.5 text-[11px] text-dim" role="presentation">Top rated</li>}
          {results.length === 0 ? <li className="px-3 py-3 text-[13px] text-muted" role="presentation">No player matches “{q}”.</li> : results.map((o, i) => (
            <li key={o.id} id={`${id}-opt-${o.id}`} role="option" aria-selected={i === active}
                onMouseDown={(e) => { e.preventDefault(); choose(o); }} onMouseEnter={() => setActive(i)}
                className={`flex cursor-pointer items-center gap-2.5 px-3 py-2 text-[13px] ${i === active ? "bg-card-hover" : ""}`}>
              <PlayerPhoto name={o.name} src={o.photo} size={24} />
              <span className="min-w-0 flex-1 truncate">{o.name}</span>
              <span className="fig text-[11px] text-dim">{tourName(o.tour)} · Elo #{o.elo_rank}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

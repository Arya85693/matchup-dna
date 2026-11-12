"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { PlayerPhoto } from "../PlayerPhoto";

export type PickOption = { id: number; name: string; tour: "ATP" | "WTA"; photo: string | null; elo_rank: number };

/** Rows drawn at a time: the list grows as it is scrolled (or arrowed) towards the end, so a tour of thousands of
 *  players never renders them all at once. */
const STEP = 40;

/**
 * Search any player by name (combobox pattern: type, arrow keys to move, Enter to choose, Esc to close). The list
 * scrolls: with nothing typed it is every player of the tour by Elo rank, and typing narrows it.
 */
export function PlayerPicker({ options, value, onPick, label, exclude, tourName = (t) => t }: {
  options: PickOption[]; value: PickOption | null; onPick: (id: number) => void; label: string; exclude?: number | null;
  tourName?: (tour: PickOption["tour"]) => string;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [shown, setShown] = useState(STEP);
  const results = useMemo(() => {
    const query = q.trim().toLowerCase();
    const pool = options.filter((o) => o.id !== exclude);
    const hits = query ? pool.filter((o) => o.name.toLowerCase().includes(query)) : pool;
    return hits.sort((a, b) => a.elo_rank - b.elo_rank || a.name.localeCompare(b.name));
  }, [options, q, exclude]);
  const visible = results.slice(0, shown);
  const more = () => setShown((s) => Math.min(results.length, s + STEP));
  const choose = (o: PickOption) => { onPick(o.id); setQ(""); setOpen(false); input.current?.blur(); };
  const reset = () => { setActive(0); setShown(STEP); list.current?.scrollTo({ top: 0 }); };

  // Keep the highlighted player in view as the arrow keys move. Keyed on the highlighted id only, so scrolling with
  // the mouse (which adds rows) never pulls the list back.
  const activeId = visible[active]?.id;
  useEffect(() => {
    if (open && activeId !== undefined) document.getElementById(`${id}-opt-${activeId}`)?.scrollIntoView({ block: "nearest" });
  }, [activeId, open, id]);

  return (
    <div className="relative">
      <label htmlFor={`${id}-input`} className="sr-only">{label}</label>
      <div className="flex items-center gap-2 rounded-lg border border-border bg-bg px-3 py-2 focus-within:border-accent">
        <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" className="shrink-0 text-dim"><circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="m10.5 10.5 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
        <input ref={input} id={`${id}-input`} role="combobox" aria-expanded={open} aria-controls={`${id}-list`} aria-autocomplete="list"
               aria-activedescendant={open && visible[active] ? `${id}-opt-${visible[active]!.id}` : undefined}
               value={q} placeholder={value ? `Change ${value.name}` : "Search a player"} autoComplete="off"
               onChange={(e) => { setQ(e.target.value); setOpen(true); reset(); }}
               onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 120)}
               onKeyDown={(e) => {
                 if (e.key === "ArrowDown") {
                   e.preventDefault(); setOpen(true);
                   const next = Math.min(results.length - 1, active + 1);
                   setActive(next);
                   if (next >= shown - 5) more();
                 }
                 if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
                 if (e.key === "Enter" && visible[active]) { e.preventDefault(); choose(visible[active]!); }
                 if (e.key === "Escape") { setOpen(false); setQ(""); reset(); }
               }}
               className="w-full bg-transparent text-[13px] outline-none placeholder:text-dim" />
      </div>
      {open && (
        <div className="absolute inset-x-0 top-full z-30 mt-1 overflow-hidden rounded-lg border border-border-strong bg-bg shadow-xl"
             onMouseDown={(e) => e.preventDefault() /* dragging the scrollbar must not blur the search box and close the list */}>
          <p className="flex items-baseline justify-between gap-3 border-b border-border px-3 py-2 text-[11px] text-dim">
            <span>{q ? `${results.length.toLocaleString("en-GB")} ${results.length === 1 ? "player matches" : "players match"}` : "All players, by Elo rank"}</span>
            {results.length > STEP && <span className="fig">Scroll for more</span>}
          </p>
          <ul ref={list} id={`${id}-list`} role="listbox" aria-label={label}
              onScroll={(e) => { const el = e.currentTarget; if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) more(); }}
              className="max-h-[min(360px,50vh)] overflow-y-auto overscroll-contain py-1 [scrollbar-color:var(--color-border-strong)_transparent] [scrollbar-width:thin]">
            {results.length === 0 ? <li className="px-3 py-3 text-[13px] text-muted" role="presentation">No player matches “{q}”.</li> : visible.map((o, i) => (
              <li key={o.id} id={`${id}-opt-${o.id}`} role="option" aria-selected={i === active}
                  onMouseDown={(e) => { e.preventDefault(); choose(o); }} onMouseEnter={() => setActive(i)}
                  className={`flex cursor-pointer items-center gap-2.5 px-3 py-2 text-[13px] ${i === active ? "bg-card-hover" : ""}`}>
                <PlayerPhoto name={o.name} src={o.photo} size={24} />
                <span className="min-w-0 flex-1 truncate">{o.name}</span>
                <span className="fig text-[11px] text-dim">{tourName(o.tour)} · Elo #{o.elo_rank}</span>
              </li>
            ))}
            {visible.length < results.length && (
              <li role="presentation" className="px-3 py-2 text-center text-[11px] text-dim">
                Showing {visible.length.toLocaleString("en-GB")} of {results.length.toLocaleString("en-GB")}
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

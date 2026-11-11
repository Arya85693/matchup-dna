"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import type { HistoryListing } from "@/lib/contract";
import { playerSlug } from "@/lib/format";
import { Spark } from "./EloChart";
import { InfoTip } from "./InfoTip";
import { PlayerPhoto } from "./PlayerPhoto";
import { SurfaceDot } from "./ui";

type Tour = "ATP" | "WTA";
type Surface = "All" | "Hard" | "Clay" | "Grass";
type Band = "any" | "2000" | "1800" | "1600" | "below";
type Move = "any" | "up" | "down";
type SortKey = "elo_rank" | "name" | "elo" | "Hard" | "Clay" | "Grass" | "season" | "change";
type Sort = { key: SortKey; dir: "asc" | "desc" };

const PAGE = 50;
const SURFACES = ["Hard", "Clay", "Grass"] as const;
const FIRST_DIR: Record<SortKey, "asc" | "desc"> = {
  elo_rank: "asc", name: "asc", elo: "desc", Hard: "desc", Clay: "desc", Grass: "desc", season: "desc", change: "desc",
};
const BANDS: [Band, string, (e: number) => boolean][] = [
  ["any", "Any Elo", () => true], ["2000", "2000+", (e) => e >= 2000], ["1800", "1800+", (e) => e >= 1800],
  ["1600", "1600+", (e) => e >= 1600], ["below", "Below 1600", (e) => e < 1600],
];

function value(p: HistoryListing, key: SortKey): number | string | null {
  switch (key) {
    case "elo_rank": return p.elo_rank;
    case "name": return p.name.toLowerCase();
    case "elo": return p.elo;
    case "season": { const [w, l] = p.season; return w + l ? w / (w + l) + w / 1e6 : null; }
    case "change": return p.elo_change_90d;
    default: return p.surfaces[key];
  }
}

function SortHeader({ k, label, tip, className = "", align = "right", sort, onSort }: {
  k: SortKey; label: React.ReactNode; tip?: React.ReactNode; className?: string; align?: "left" | "right"; sort: Sort; onSort: (k: SortKey) => void;
}) {
  const active = sort.key === k;
  return (
    <th scope="col" aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"} className={`px-1.5 py-2 sm:px-2.5 font-normal ${align === "right" ? "text-right" : "text-left"} ${className}`}>
      <span className={`inline-flex items-center gap-1.5 ${align === "right" ? "flex-row-reverse" : ""}`}>
        {tip}
        <button type="button" onClick={() => onSort(k)} className={`inline-flex items-center gap-1 whitespace-nowrap transition-colors ${active ? "text-text" : "hover:text-text"}`}>
          {label}
          <svg width="8" height="10" viewBox="0 0 8 10" aria-hidden="true" className={active ? "text-accent" : "text-border-strong"}>
            <path d="M4 1 7 4H1z" fill="currentColor" opacity={active && sort.dir === "asc" ? 1 : active ? 0.25 : 1} />
            <path d="M4 9 1 6h6z" fill="currentColor" opacity={active && sort.dir === "desc" ? 1 : active ? 0.25 : 1} />
          </svg>
        </button>
      </span>
    </th>
  );
}

const seg = "rounded-[5px] px-2.5 py-1 text-[12px] transition-colors";
const segOn = "bg-card-hover text-text";
const segOff = "text-muted hover:text-text";

/** Wording that differs between the main-tour board and the ITF board; the table itself is the same. */
const TEXT = {
  main: {
    tours: { ATP: "ATP", WTA: "WTA" },
    position: (tour: string) => <>Position among active {tour} players by Matchup DNA&apos;s Elo rating.</>,
    elo: <>A rating built from every past result, weighted by the opponent&apos;s strength. Winning against stronger players raises it more.</>,
    season: <>Wins and losses in completed tour-level matches this calendar year. Sorted by win rate.</>,
  },
  itf: {
    tours: { ATP: "ITF Men", WTA: "ITF Women" },
    position: (tour: string) => <>Position among the listed {tour} players by the ITF model&apos;s Elo rating.</>,
    elo: <>The ITF model&apos;s Elo: built from results at every level, from ITF events to the Grand Slams, weighted by the opponent&apos;s strength. It moves faster while a player is new, and is not on the same scale as the main-tour Elo.</>,
    season: <>Wins and losses in completed matches at every level this calendar year. Sorted by win rate.</>,
  },
} as const;

/** The players table. `base` is where profiles and Compare live ("/players" for the main tour, "/players/itf" for
 * the ITF board); `param` is the address parameter that remembers the tour, so two boards on one page never clash. */
export function PlayersBrowser({ players, base = "/players", circuit = "main", param = "tour" }: {
  players: HistoryListing[]; base?: string; circuit?: "main" | "itf"; param?: string;
}) {
  const text = TEXT[circuit];
  const router = useRouter();
  const search = useRef<HTMLInputElement>(null);
  const [tour, setTour] = useState<Tour>("ATP");
  const [q, setQ] = useState("");
  const [surface, setSurface] = useState<Surface>("All");
  const [band, setBand] = useState<Band>("any");
  const [move, setMove] = useState<Move>("any");
  const [sort, setSort] = useState<Sort>({ key: "elo_rank", dir: "asc" });
  const [limit, setLimit] = useState(PAGE);

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get(param);
    if (t === "WTA" || t === "ATP") setTour(t);
  }, [param]);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    if (tour === "ATP") q.delete(param); else q.set(param, tour);
    const rest = q.toString();
    window.history.replaceState(null, "", rest ? `?${rest}` : window.location.pathname);
    setLimit(PAGE);
  }, [tour, param]);

  const counts = useMemo(() => ({ ATP: players.filter((p) => p.tour === "ATP").length, WTA: players.filter((p) => p.tour === "WTA").length }), [players]);
  const rows = useMemo(() => {
    const query = q.trim().toLowerCase();
    const test = BANDS.find((b) => b[0] === band)![2];
    const list = players.filter((p) => p.tour === tour
      && (!query || p.name.toLowerCase().includes(query))
      && (surface === "All" || p.surface_matches[surface] > 0)
      && test(p.elo)
      && (move === "any" || (p.elo_change_90d !== null && (move === "up" ? p.elo_change_90d > 0 : p.elo_change_90d < 0))));
    const sign = sort.dir === "asc" ? 1 : -1;
    return list.sort((a, b) => {
      const x = value(a, sort.key), y = value(b, sort.key);
      if (x === null && y === null) return a.elo_rank - b.elo_rank;
      if (x === null) return 1;                       // missing values always last
      if (y === null) return -1;
      if (x < y) return -sign;
      if (x > y) return sign;
      return a.elo_rank - b.elo_rank;
    });
  }, [players, tour, q, surface, band, move, sort]);

  const filtered = q || surface !== "All" || band !== "any" || move !== "any";
  const reset = () => { setQ(""); setSurface("All"); setBand("any"); setMove("any"); setSort({ key: "elo_rank", dir: "asc" }); setLimit(PAGE); };
  const sortBy = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: FIRST_DIR[key] }));
  const chooseSurface = (s: Surface) => {
    setSurface(s);
    if (s !== "All" && (sort.key === "elo_rank" || sort.key === "elo" || SURFACES.includes(sort.key as never))) setSort({ key: s, dir: "desc" });
    if (s === "All" && SURFACES.includes(sort.key as never)) setSort({ key: "elo_rank", dir: "asc" });
  };

  return (
    <div className="grid gap-4">
      {/* Toolbar */}
      <div className="grid gap-3 rounded-lg border border-border bg-card/50 p-3">
        <div className="flex flex-wrap items-center gap-3">
          <div role="group" aria-label="Tour" className="inline-flex gap-0.5 rounded-md border border-border bg-bg p-0.5">
            {(["ATP", "WTA"] as const).map((t) => (
              <button key={t} aria-pressed={tour === t} onClick={() => setTour(t)} className={`${seg} px-3 ${tour === t ? segOn : segOff}`}>
                {text.tours[t]} <span className="fig ml-1 text-[11px] text-dim">{counts[t]}</span>
              </button>
            ))}
          </div>
          <label className="relative min-w-[200px] flex-1">
            <span className="sr-only">Search players</span>
            <svg className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-dim" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="m10.5 10.5 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
            <input ref={search} id="player-search" type="search" value={q} onChange={(e) => { setQ(e.target.value); setLimit(PAGE); }}
                   onKeyDown={(e) => { if (e.key === "Escape") setQ(""); }} placeholder={`Search ${counts[tour]} ${text.tours[tour]} players`} autoComplete="off"
                   className="w-full rounded-md border border-border bg-bg py-1.5 pl-8 pr-8 text-[13px] outline-none transition-colors placeholder:text-dim focus:border-accent" />
            {q && <button type="button" onClick={() => { setQ(""); search.current?.focus(); }} aria-label="Clear search" className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-1 text-[12px] text-dim hover:text-text">✕</button>}
          </label>
          <Link href={`${base}/compare?tour=${tour}`} className="inline-flex items-center gap-2 rounded-md bg-accent px-3 py-1.5 text-[13px] font-medium text-bg transition hover:brightness-110">
            <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3 2 6l3 3M2 6h9M11 7l3 3-3 3M14 10H5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
            Compare players
          </Link>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px]">
          <span className="flex items-center gap-2">
            <span className="text-dim">Surface</span>
            <span role="group" aria-label="Surface" className="inline-flex gap-0.5 rounded-md border border-border bg-bg p-0.5">
              {(["All", ...SURFACES] as Surface[]).map((s) => (
                <button key={s} aria-pressed={surface === s} onClick={() => chooseSurface(s)} className={`${seg} inline-flex items-center gap-1.5 ${surface === s ? segOn : segOff}`}>
                  {s !== "All" && <SurfaceDot surface={s} />}{s === "All" ? "All" : s}
                </button>
              ))}
            </span>
          </span>
          <label className="flex items-center gap-2">
            <span className="text-dim">Elo</span>
            <select id="elo-band" value={band} onChange={(e) => { setBand(e.target.value as Band); setLimit(PAGE); }}
                    className="rounded-md border border-border bg-bg px-2 py-1 text-[12px] text-text outline-none focus:border-accent">
              {BANDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <span className="flex items-center gap-2">
            <span className="text-dim">90 days</span>
            <span role="group" aria-label="Elo movement in the last 90 days" className="inline-flex gap-0.5 rounded-md border border-border bg-bg p-0.5">
              {([["any", "Any"], ["up", "Rising"], ["down", "Falling"]] as [Move, string][]).map(([v, l]) => (
                <button key={v} aria-pressed={move === v} onClick={() => setMove(v)} className={`${seg} ${move === v ? segOn : segOff}`}>{l}</button>
              ))}
            </span>
          </span>
          <span className="ml-auto flex items-center gap-3 text-dim" aria-live="polite">
            <span className="fig">{rows.length} of {counts[tour]}</span>
            {filtered && <button type="button" onClick={reset} className="link">Reset</button>}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-[13px]">
          <caption className="sr-only">{text.tours[tour]} players, sorted by {sort.key} {sort.dir === "asc" ? "ascending" : "descending"}</caption>
          <thead className="bg-card">
            <tr className="border-b border-border text-[11px] text-dim">
              <SortHeader sort={sort} onSort={sortBy} k="elo_rank" label="Elo #" align="left" className="hidden w-14 sm:table-cell" tip={<InfoTip label="Elo position" align="start">{text.position(text.tours[tour])}</InfoTip>} />
              <SortHeader sort={sort} onSort={sortBy} k="name" label="Player" align="left" />
              <SortHeader sort={sort} onSort={sortBy} k="elo" label="Elo" tip={<InfoTip label="Elo">{text.elo}</InfoTip>} />
              {SURFACES.map((s, i) => (
                <SortHeader sort={sort} onSort={sortBy} key={s} k={s} className={`hidden lg:table-cell ${surface === s ? "bg-accent-soft" : ""}`}
                        label={<span className="inline-flex items-center gap-1.5"><SurfaceDot surface={s} />{s}</span>}
                        tip={i === 0 ? <InfoTip label="surface Elo">Elo built from matches on that surface, blended half and half with overall Elo.</InfoTip> : undefined} />
              ))}
              <SortHeader sort={sort} onSort={sortBy} k="season" label="Season" className="hidden md:table-cell" tip={<InfoTip label="season record">{text.season}</InfoTip>} />
              <SortHeader sort={sort} onSort={sortBy} k="change" label="90 days" tip={<InfoTip label="90-day change" align="end">Change in Elo over the last 90 days. Blank when the player has no rating from 90 days ago.</InfoTip>} />
              <th scope="col" className="hidden py-2 pl-2.5 pr-4 text-right font-normal sm:table-cell">Trend</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.length === 0 ? (
              <tr><td colSpan={12} className="px-4 py-14 text-center">
                <p className="text-text">No players match{q ? ` “${q}”` : " these filters"}.</p>
                <button type="button" onClick={reset} className="link mt-2 text-[13px]">Clear search and filters</button>
              </td></tr>
            ) : rows.slice(0, limit).map((p) => {
              const [w, l] = p.season;
              return (
                <tr key={p.id} onClick={(e) => { if (!(e.target as HTMLElement).closest("a,button,input,label,svg[tabindex]")) router.push(`${base}/${playerSlug(p.tour, p.id)}`); }}
                    className="group cursor-pointer transition-colors hover:bg-card">
                  <td className="fig hidden py-2 pl-4 pr-1.5 text-[12px] text-dim sm:table-cell sm:pr-2.5">{p.elo_rank}</td>
                  <td className="max-w-[170px] py-2 pl-3 pr-1.5 sm:max-w-[260px] sm:px-2.5">
                    <span className="flex min-w-0 items-center gap-2.5">
                      <PlayerPhoto name={p.name} src={p.photo} size={26} />
                      <span className="min-w-0">
                    <Link href={`${base}/${playerSlug(p.tour, p.id)}`} className="block truncate font-medium outline-offset-2 group-hover:text-accent">{p.name}</Link>
                    <span className="fig text-[11px] text-dim sm:hidden">Elo #{p.elo_rank}</span>
                      </span>
                    </span>
                  </td>
                  <td className="fig px-1.5 py-2 sm:px-2.5 text-right font-medium">{Math.round(p.elo)}</td>
                  {SURFACES.map((s) => (
                    <td key={s} className={`fig hidden px-1.5 py-2 sm:px-2.5 text-right lg:table-cell ${surface === s ? "bg-accent-soft text-text" : "text-muted"}`}
                        title={`${p.surface_matches[s]} rated matches on ${s.toLowerCase()}`}>
                      {p.surface_matches[s] ? Math.round(p.surfaces[s]) : <span className="text-dim">—</span>}
                    </td>
                  ))}
                  <td className="fig hidden px-1.5 py-2 sm:px-2.5 text-right text-muted md:table-cell">{w + l ? `${w}–${l}` : <span className="text-dim">—</span>}</td>
                  <td className={`fig px-1.5 py-2 sm:px-2.5 text-right ${p.elo_change_90d === null ? "text-dim" : p.elo_change_90d > 0 ? "text-pos" : p.elo_change_90d < 0 ? "text-neg" : "text-muted"}`}>
                    {p.elo_change_90d === null ? "—" : `${p.elo_change_90d > 0 ? "+" : p.elo_change_90d < 0 ? "−" : ""}${Math.abs(Math.round(p.elo_change_90d))}`}
                  </td>
                  <td className="hidden py-1.5 pl-2.5 pr-4 text-right sm:table-cell"><Spark points={p.spark} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > limit && (
        <button type="button" onClick={() => setLimit((n) => n + PAGE)} className="mx-auto rounded-md border border-border px-4 py-2 text-[13px] text-muted transition-colors hover:bg-card hover:text-text">
          Show {Math.min(PAGE, rows.length - limit)} more <span className="text-dim">({rows.length - limit} left)</span>
        </button>
      )}
      <p className="text-[12px] text-dim">A dash in a surface column means no rated matches on that surface. Click any row to open the profile, or use Compare players to put two side by side.</p>
    </div>
  );
}

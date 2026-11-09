"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { HistoryPlayer } from "@/lib/contract";
import { playerSlug, roundLabel } from "@/lib/format";
import { EloChart } from "../EloChart";
import { PlayerPhoto } from "../PlayerPhoto";
import { PhotoCredit } from "../PhotoCredit";
import { Segmented } from "../lab/parts";
import { SurfaceDot } from "../ui";
import { HeadToHead } from "./HeadToHead";
import { PlayerPicker, type PickOption } from "./PlayerPicker";

type Stat = { label: string; a: number | null; b: number | null; fmt: (v: number) => string; better: "high" | "low" | null; bar: boolean; note?: string };

function stats(A: HistoryPlayer, B: HistoryPlayer): Stat[] {
  const pct = (w: number, l: number) => (w + l ? w / (w + l) : null);
  const int = (v: number) => Math.round(v).toLocaleString("en-GB");
  return [
    { label: "Elo rating", a: A.elo, b: B.elo, fmt: int, better: "high", bar: true },
    { label: "Hard-court Elo", a: A.surfaces.Hard.elo, b: B.surfaces.Hard.elo, fmt: int, better: "high", bar: true },
    { label: "Clay-court Elo", a: A.surfaces.Clay.elo, b: B.surfaces.Clay.elo, fmt: int, better: "high", bar: true },
    { label: "Grass-court Elo", a: A.surfaces.Grass.elo, b: B.surfaces.Grass.elo, fmt: int, better: "high", bar: true },
    { label: `${A.season.year} win rate`, a: pct(...A.season.All), b: pct(...B.season.All), fmt: (v) => `${Math.round(v * 100)}%`, better: "high", bar: true },
    { label: `${A.season.year} matches won`, a: A.season.All[0], b: B.season.All[0], fmt: int, better: "high", bar: true },
    { label: "Elo change, 90 days", a: A.elo_change_90d, b: B.elo_change_90d, fmt: (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(Math.round(v))}`, better: "high", bar: false },
    { label: "Rated matches", a: A.rated_matches, b: B.rated_matches, fmt: int, better: null, bar: true },
  ];
}

type Tour = "ATP" | "WTA";

export function CompareView({ options: everyone, a, b, tour }: { options: PickOption[]; a: HistoryPlayer | null; b: HistoryPlayer | null; tour: Tour }) {
  const router = useRouter();
  const options = everyone.filter((o) => o.tour === tour);      // ATP and WTA ratings are separate pools: compare within one tour
  const go = (na: number | null, nb: number | null, t: Tour = tour) => {
    const q = new URLSearchParams({ tour: t });
    if (na !== null) q.set("a", String(na));
    if (nb !== null) q.set("b", String(nb));
    router.push(`/players/compare?${q}`, { scroll: false });
  };
  const opt = (p: HistoryPlayer | null) => (p ? options.find((o) => o.id === p.id) ?? null : null);
  const sides = [
    { p: a, pick: (id: number) => go(id, b?.id ?? null), clear: () => go(null, b?.id ?? null), label: "First player" },
    { p: b, pick: (id: number) => go(a?.id ?? null, id), clear: () => go(a?.id ?? null, null), label: "Second player" },
  ];

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Tour" value={tour} onChange={(t) => { if (t !== tour) go(null, null, t); }}
                   options={[["ATP", `ATP · ${everyone.filter((o) => o.tour === "ATP").length}`], ["WTA", `WTA · ${everyone.filter((o) => o.tour === "WTA").length}`]]} />
        <p className="text-[12px] text-dim">Players are compared within one tour.</p>
      </div>
      {/* The two players, facing each other */}
      <section aria-label="Players" className="grid gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-[minmax(0,1fr)_64px_minmax(0,1fr)]">
        {sides.map((s, i) => (
          <div key={i} className={`grid content-start gap-5 bg-card p-5 sm:p-6 ${i === 1 ? "md:order-3" : ""}`}>
            <PlayerPicker key={tour} options={options} value={opt(s.p)} onPick={s.pick} label={`${s.label} (${tour})`} exclude={(i === 0 ? b : a)?.id ?? null} />
            {s.p ? (
              <div className={`flex items-center gap-4 ${i === 1 ? "md:flex-row-reverse md:text-right" : ""}`}>
                <PlayerPhoto name={s.p.name} src={s.p.photo} size={96} />
                <div className="min-w-0">
                  <Link href={`/players/${playerSlug(s.p.tour, s.p.id)}`} className="block truncate text-[22px] font-semibold leading-tight hover:text-accent">{s.p.name}</Link>
                  <p className="mt-1 text-[12px] text-dim">{s.p.tour} · Elo #{s.p.elo_rank} · last played {s.p.last_match}</p>
                  <p className="fig mt-3 text-[32px] font-medium leading-none text-text">{Math.round(s.p.elo)}<span className="ml-1.5 text-[12px] font-normal text-dim">Elo</span></p>
                  <PhotoCredit credit={s.p.photo_credit} className="mt-2" />
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-4 text-muted">
                <span className="inline-flex size-24 items-center justify-center rounded-full border border-dashed border-border-strong text-[28px] text-dim" aria-hidden="true">?</span>
                <p className="text-[13px]">Search for a player to add them here.</p>
              </div>
            )}
            {s.p && <button type="button" onClick={s.clear} className={`w-fit text-[12px] text-dim hover:text-text ${i === 1 ? "md:justify-self-end" : ""}`}>Remove</button>}
          </div>
        ))}
        <div className="hidden items-center justify-center bg-card md:order-2 md:flex"><span className="fig text-[13px] text-dim">vs</span></div>
      </section>

      {a && b ? (
        <>
          <HeadToHead a={a} b={b} />
          <section aria-label="Statistics" className="rounded-xl border border-border bg-card">
            <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 border-b border-border px-5 py-3 text-[12px]">
              <span className="truncate font-medium">{a.name}</span><span className="text-dim">Statistic</span><span className="truncate text-right font-medium">{b.name}</span>
            </div>
            <ul className="divide-y divide-border">
              {stats(a, b).map((s) => <StatRow key={s.label} s={s} />)}
            </ul>
          </section>

          <section aria-label="Elo over time" className="rounded-xl border border-border bg-card p-5">
            <h2 className="mb-4 text-[13px] font-medium">Elo over time</h2>
            <EloChart series={[{ name: a.name, points: a.series }, { name: b.name, points: b.series }]} />
          </section>

          <section aria-label="Recent results" className="grid gap-6 md:grid-cols-2">
            {[a, b].map((p) => (
              <div key={p.id} className="rounded-xl border border-border bg-card">
                <div className="flex items-center justify-between border-b border-border px-5 py-3">
                  <h2 className="text-[13px] font-medium">{p.name}: recent results</h2>
                  <span className="flex gap-1" aria-label={`Last ${Math.min(5, p.recent.length)}: ${p.recent.slice(0, 5).map((r) => (r.won ? "W" : "L")).join(" ")}`}>
                    {p.recent.slice(0, 5).map((r, i) => (
                      <span key={i} className={`inline-flex size-5 items-center justify-center rounded text-[10px] font-semibold ${r.won ? "bg-pos/20 text-pos" : "bg-neg/20 text-neg"}`}>{r.won ? "W" : "L"}</span>
                    ))}
                  </span>
                </div>
                <ul className="divide-y divide-border">
                  {p.recent.slice(0, 6).map((r, i) => (
                    <li key={i} className="flex items-center justify-between gap-3 px-5 py-2.5 text-[13px]">
                      <span className="min-w-0">
                        <span className="block truncate">{r.won ? "Beat" : "Lost to"} {r.opponent}</span>
                        <span className="flex items-center gap-1.5 text-[11px] text-dim"><SurfaceDot surface={r.surface} />{r.event} · {roundLabel(r.round)} · {r.date}</span>
                      </span>
                      <span className={`text-[12px] font-medium ${r.won ? "text-pos" : "text-neg"}`}>{r.won ? "W" : "L"}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>
          <p className="text-[12px] text-dim">A comparison of past results from the match history, not a match forecast.</p>
        </>
      ) : (
        <div className="rounded-xl border border-dashed border-border-strong px-6 py-12 text-center text-[13px] text-muted">
          {a || b ? `Choose a second ${tour} player to see them side by side.` : `Choose two ${tour} players to compare their head to head, ratings, surface strengths, season and recent form.`}
        </div>
      )}
    </div>
  );
}

/** Opta-style row: each side's bar grows from the centre in proportion to the pair; the better side is teal. */
function StatRow({ s }: { s: Stat }) {
  const { a, b } = s;
  const max = Math.max(Math.abs(a ?? 0), Math.abs(b ?? 0)) || 1;
  const aBetter = s.better && a !== null && b !== null && a !== b ? (s.better === "high" ? a > b : a < b) : null;
  const side = (v: number | null, wins: boolean | null, left: boolean) => (
    <div className={`flex items-center gap-3 ${left ? "flex-row-reverse" : ""}`}>
      <div className={`flex h-2 flex-1 ${left ? "justify-end" : ""}`}>
        {v !== null && s.bar && <span className={`anim-fill h-full rounded-full ${wins ? "bg-accent" : "bg-[#3b4a5c]"}`} style={{ width: `${(Math.abs(v) / max) * 100}%`, transformOrigin: left ? "right" : "left" }} />}
      </div>
      <span className={`fig w-16 shrink-0 text-[15px] ${left ? "text-left" : "text-right"} ${wins ? "font-semibold text-text" : "text-muted"}`}>{v === null ? "—" : s.fmt(v)}</span>
    </div>
  );
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_120px_minmax(0,1fr)] items-center gap-3 px-5 py-3 transition-colors hover:bg-card-hover sm:grid-cols-[minmax(0,1fr)_170px_minmax(0,1fr)]">
      {side(a, aBetter === true, true)}
      <span className="text-center text-[12px] text-muted">{s.label}</span>
      {side(b, aBetter === false, false)}
    </li>
  );
}

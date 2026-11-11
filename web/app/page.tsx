import Image from "next/image";
import Link from "next/link";
import hero from "@/public/images/hero-clay.jpg";
import { HEADLINES } from "@/lib/research";
import { getHistoryIndex, getIndex, getItf, getItfArchive, getItfHistoryIndex, getItfMatches, getStatus } from "@/lib/snapshot";
import { CountUp } from "@/components/CountUp";
import { FeaturedCarousel, HowItWorks, TopPlayers } from "@/components/HomeWidgets";
import { IconArchive, IconLab, IconMatches, IconMethod } from "@/components/icons";

export const revalidate = 60;

const UPCOMING = new Set(["scheduled", "in_progress", "postponed", "suspended"]);
const delay = (ms: number) => ({ animationDelay: `${ms}ms` });

export default async function Home() {
  const [index, players, status, itf, itfIndex, itfPlayers, itfArchive] = await Promise.all([
    getIndex(), getHistoryIndex(), getStatus(), getItf(), getItfMatches(), getItfHistoryIndex(), getItfArchive(),
  ]);
  const matches = index.ok ? index.data.matches : [];
  const featured = matches.filter((m) => UPCOMING.has(m.state) && m.start && m.forecasts.tournament_start.available)
    .sort((a, b) => Number(b.forecasts.round_aware.available) - Number(a.forecasts.round_aware.available));
  const itfUpcoming = itfIndex.ok
    ? itfIndex.data.matches.filter((m) => UPCOMING.has(m.state) && m.start && m.forecasts.tournament_start.available).length : null;

  // One row for both circuits, never double counting:
  // - players on both boards (main-tour and ITF ids are the same Sackmann ids) count once;
  // - matches: the main tour's history (counted by every forecasting run) plus the ITF model's (counted by every ITF
  //   run), less the main-tour matches the ITF history also holds (counted by the daily ITF players export). That
  //   last count can be up to a day behind, so the total is rounded down to the thousand.
  const mainIds = players.ok ? players.data.players.map((p) => `${p.tour}-${p.id}`) : [];
  const itfIds = itfPlayers.ok ? itfPlayers.data.players.map((p) => `${p.tour}-${p.id}`) : [];
  // Until a run has published a count (or if one is ever missing), the last counted figures stand in, shown with a
  // "+": a history only grows, so an older count is always a true minimum. Counted on 11 November 2026.
  const live = {
    main: status.ok ? status.data.history?.matches ?? null : null,
    itf: itf.ok ? itf.data.history?.matches ?? null : null,
    overlap: itfPlayers.ok ? itfPlayers.data.history?.main_tour_matches ?? null : null,
  };
  const mainMatches = live.main ?? 364_207;
  const itfMatches = live.itf ?? 890_882;
  const overlap = live.overlap ?? 93_375;
  // Shown to three significant figures, rounded down ("1.16M+"). The overlap only grows too, so a stand-in for it
  // could overstate the total by a few hundred matches: the rounding down covers that.
  const allMatches = mainMatches + itfMatches - overlap;
  const mainForecasts = status.ok ? status.data.counts.forecasts : null;
  const itfForecasts = itfArchive.ok ? itfArchive.data.entries.length : null;
  const n = (v: number | null) => (v === null ? "—" : v.toLocaleString("en-US"));
  const sum = (a: number | null, b: number | null) => (a === null && b === null ? null : (a ?? 0) + (b ?? 0));
  const stats: { value: number | null; suffix?: string; short?: boolean; label: string; split: [string, string] }[] = [
    { value: mainIds.length || itfIds.length ? new Set([...mainIds, ...itfIds]).size : null, label: "players rated",
      split: [`${n(players.ok ? mainIds.length : null)} main tour`, `${n(itfPlayers.ok ? itfIds.length : null)} ITF`] },
    { value: allMatches, suffix: "+", short: true, label: "matches in the history",
      split: [`${n(mainMatches)}${live.main === null ? "+" : ""} main tour`, `${n(itfMatches)}${live.itf === null ? "+" : ""} ITF`] },
    { value: sum(mainForecasts, itfForecasts), label: "forecasts locked so far", split: [`${n(mainForecasts)} main tour`, `${n(itfForecasts)} ITF`] },
    { value: sum(featured.length, itfUpcoming), label: "upcoming forecasts", split: [`${n(featured.length)} main tour`, `${n(itfUpcoming)} ITF`] },
  ];

  return (
    <div className="grid gap-14">
      {/* Hero: the clay-court photo fades into the page; the headline sits on its dark side */}
      <section className="relative isolate -mx-4 overflow-hidden border-y border-border sm:mx-0 sm:rounded-2xl sm:border">
        <div className="absolute inset-0 -z-10 lg:left-[34%]">
          <Image src={hero} alt="" fill priority placeholder="blur" sizes="(min-width: 1024px) 60vw, 100vw"
                 className="anim-zoom object-cover object-[50%_28%]" />
          <div className="absolute inset-0" style={{ background: "linear-gradient(90deg, var(--color-bg) 0%, rgba(16,21,29,0.75) 30%, rgba(16,21,29,0.15) 65%, rgba(16,21,29,0) 100%)" }} />
          <div className="absolute inset-0" style={{ background: "linear-gradient(0deg, rgba(16,21,29,0.85) 0%, rgba(16,21,29,0) 35%)" }} />
          <div className="absolute inset-0 bg-bg/60 lg:hidden" />
        </div>
        <div className="max-w-[640px] px-6 py-16 sm:px-10 lg:py-28">
          <p className="anim-rise inline-flex items-center gap-2 rounded-full border border-border-strong bg-bg/70 px-3 py-1 text-[12px] text-muted" style={delay(0)}>
            <span className="size-1.5 animate-pulse rounded-full bg-pos" aria-hidden="true" /> ATP, WTA and ITF forecasts, updated every 15 minutes (ITF every hour)
          </p>
          <h1 className="anim-rise mt-6 text-[36px] font-semibold leading-[1.08] sm:text-[52px]" style={delay(90)}>
            Who wins the next match, and how sure should we be?
          </h1>
          <p className="anim-rise mt-6 max-w-[50ch] text-[16px] leading-relaxed text-text/80" style={delay(180)}>
            Matchup DNA rates every pro tennis player from their full match history, gives each upcoming match a win
            probability, and locks every forecast before the first serve so anyone can check how it does.
          </p>
          <div className="anim-rise mt-8 flex flex-wrap gap-3" style={delay(270)}>
            <Link href="/matches" className="rounded-lg bg-accent px-5 py-3 text-[14px] font-medium text-bg transition hover:brightness-110">See today&apos;s forecasts</Link>
            <Link href="/players" className="rounded-lg border border-border-strong bg-bg/60 px-5 py-3 text-[14px] text-text transition hover:bg-card">Explore the players</Link>
          </div>
        </div>
      </section>

      <section aria-label="In numbers" className="anim-rise grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border lg:grid-cols-4" style={delay(360)}>
        {stats.map((s) => (
          <div key={s.label} className="bg-bg px-5 py-5">
            <p className="text-[28px] font-semibold">{s.value === null ? "—" : <><CountUp value={s.value} short={s.short} />{s.suffix}</>}</p>
            <p className="mt-1 text-[13px] text-muted">{s.label}</p>
            <p className="fig mt-2 text-[11px] text-dim">
              <span className="block sm:inline">{s.split[0]}</span><span className="hidden sm:inline"> · </span><span className="block sm:inline">{s.split[1]}</span>
            </p>
          </div>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="grid content-start gap-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[20px] font-semibold">Featured forecasts</h2>
            <Link href="/matches" className="link text-[13px]">All matches</Link>
          </div>
          {featured.length > 0 ? <FeaturedCarousel matches={featured} /> : (
            <div className="card p-6 text-muted">No upcoming forecasts right now. New ones are issued every 15 minutes.</div>
          )}
        </div>
        <div className="grid content-start gap-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[20px] font-semibold">The players</h2>
            <Link href="/players" className="link text-[13px]">All players</Link>
          </div>
          {players.ok && <TopPlayers players={players.data.players} />}
        </div>
      </section>

      <section>
        <h2 className="text-[20px] font-semibold">How a forecast is made</h2>
        <p className="mt-1.5 text-muted">Four steps, from a match result to a scored prediction.</p>
        <div className="mt-6"><HowItWorks /></div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2">
        {[
          { href: "/matches", icon: IconMatches, title: "Matches", text: "Every upcoming ATP and WTA match with its forecast, grouped by tournament." },
          { href: "/itf", icon: IconMatches, title: "ITF World Tennis Tour", text: "ITF Men and ITF Women forecasts from a separate model, tested once on matches it had never seen." },
          { href: "/lab", icon: IconLab, title: "Is it any good?", text: `Calibration, held-out tests, and the honest part: the betting market is better (${HEADLINES.marketLogLoss.toFixed(3)} vs ${HEADLINES.modelLogLoss.toFixed(3)} log loss).` },
          { href: "/archive", icon: IconArchive, title: "Forecast Archive", text: "Every forecast ever issued, timestamped and impossible to edit." },
          { href: "/methodology", icon: IconMethod, title: "How it works", text: "The data, the ratings and the model, in five short steps." },
        ].map(({ href, icon: Icon, title, text }) => (
          <Link key={href} href={href} className="card lift group flex items-start gap-4 p-5 hover:border-border-strong hover:bg-card-hover">
            <span className="mt-0.5 rounded-md border border-border p-2 text-accent"><Icon /></span>
            <span className="min-w-0">
              <span className="block font-medium">{title} <span className="inline-block text-dim transition-transform group-hover:translate-x-1">→</span></span>
              <span className="mt-1 block text-[13px] text-muted">{text}</span>
            </span>
          </Link>
        ))}
      </section>
    </div>
  );
}

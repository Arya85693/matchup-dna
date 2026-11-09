import Image from "next/image";
import Link from "next/link";
import hero from "@/public/images/hero-clay.jpg";
import { HEADLINES } from "@/lib/research";
import { getHistoryIndex, getIndex, getStatus } from "@/lib/snapshot";
import { CountUp } from "@/components/CountUp";
import { FeaturedCarousel, HowItWorks, TopPlayers } from "@/components/HomeWidgets";
import { IconArchive, IconLab, IconMatches, IconMethod } from "@/components/icons";

export const revalidate = 300;

const UPCOMING = new Set(["scheduled", "in_progress", "postponed", "suspended"]);
const delay = (ms: number) => ({ animationDelay: `${ms}ms` });

export default async function Home() {
  const [index, players, status] = await Promise.all([getIndex(), getHistoryIndex(), getStatus()]);
  const matches = index.ok ? index.data.matches : [];
  const featured = matches.filter((m) => UPCOMING.has(m.state) && m.start && m.forecasts.tournament_start.available)
    .sort((a, b) => Number(b.forecasts.round_aware.available) - Number(a.forecasts.round_aware.available));
  const stats: { value: number | null; suffix?: string; label: string }[] = [
    { value: players.ok ? players.data.players.length : null, label: "players rated" },
    { value: 360000, suffix: "+", label: "matches in the history" },
    { value: status.ok ? status.data.counts.forecasts : null, label: "forecasts locked so far" },
    { value: featured.length, label: "upcoming forecasts" },
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
            <span className="size-1.5 animate-pulse rounded-full bg-pos" aria-hidden="true" /> ATP and WTA forecasts, updated twice a day
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
            <p className="text-[28px] font-semibold">{s.value === null ? "—" : <><CountUp value={s.value} />{s.suffix}</>}</p>
            <p className="mt-1 text-[13px] text-muted">{s.label}</p>
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
            <div className="card p-6 text-muted">No upcoming forecasts right now. New ones are issued twice a day.</div>
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
          { href: "/matches", icon: IconMatches, title: "Matches", text: "Every upcoming match with its forecast, grouped by tournament." },
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

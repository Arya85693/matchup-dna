"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ago } from "@/lib/format";
import { IconArchive, IconLab, IconLogo, IconMatches, IconMethod, IconOverview, IconPlayers, IconStatus } from "./icons";

const NAV = [
  { href: "/", label: "Home", icon: IconOverview, match: (p: string) => p === "/" },
  { href: "/matches", label: "Matches", icon: IconMatches, match: (p: string) => p.startsWith("/matches") },
  { href: "/players", label: "Players", icon: IconPlayers, match: (p: string) => p.startsWith("/players") },
  { href: "/itf", label: "ITF", icon: IconMatches, match: (p: string) => p.startsWith("/itf") },
  { href: "/lab", label: "Model Lab", icon: IconLab, match: (p: string) => p.startsWith("/lab") },
  { href: "/archive", label: "Forecast Archive", icon: IconArchive, match: (p: string) => p.startsWith("/archive") },
  { href: "/methodology", label: "Methodology", icon: IconMethod, match: (p: string) => p.startsWith("/methodology") },
];

/** Data freshness from the last successful forecast run (not cache age); amber past the job's 18-hour rule. */
function Freshness({ last, staleAfter, ok }: { last: string | null; staleAfter: number; ok: boolean }) {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);
  const stale = !last || !ok || (now !== null && (now.getTime() - Date.parse(last)) / 3_600_000 > staleAfter);
  return (
    <Link href="/status" className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[12px] text-muted hover:bg-card-hover hover:text-text">
      <span className={`size-1.5 rounded-full ${stale ? "bg-warn" : "bg-pos"}`} aria-hidden="true" />
      <span suppressHydrationWarning>
        {!last ? "Data unavailable" : stale ? "Data may be out of date" : `Updated ${now ? ago(last, now) : "recently"}`}
      </span>
    </Link>
  );
}

export function Sidebar({ last, staleAfter, ok }: { last: string | null; staleAfter: number; ok: boolean }) {
  const path = usePathname() ?? "/";
  return (
    <>
      {/* Desktop: fixed sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[232px] flex-col border-r border-border bg-bg px-3 py-4 lg:flex">
        <Link href="/" className="mb-6 flex items-center gap-2.5 px-2.5 py-1.5 text-[14px] font-semibold">
          <IconLogo className="text-text" /> Matchup DNA
        </Link>
        <nav aria-label="Main" className="grid gap-0.5">
          {NAV.map(({ href, label, icon: Icon, match }) => {
            const active = match(path);
            return (
              <Link key={href} href={href} aria-current={active ? "page" : undefined}
                    className={`flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13px] transition-colors ${active ? "bg-card text-text" : "text-muted hover:bg-card-hover hover:text-text"}`}>
                <Icon className={active ? "text-accent" : ""} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto grid gap-1">
          <Freshness last={last} staleAfter={staleAfter} ok={ok} />
          <p className="flex items-center gap-2.5 px-2.5 py-2 text-[12px] text-muted">
            <IconStatus /> Source Code (Available upon Request)
          </p>
        </div>
      </aside>

      {/* Mobile: top bar with a scrolling nav */}
      <header className="sticky top-0 z-20 border-b border-border bg-bg/95 backdrop-blur lg:hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <Link href="/" className="flex items-center gap-2 text-[14px] font-semibold"><IconLogo className="text-text" /> Matchup DNA</Link>
          <Freshness last={last} staleAfter={staleAfter} ok={ok} />
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-2.5">
          {NAV.map(({ href, label, match }) => {
            const active = match(path);
            return (
              <Link key={href} href={href} aria-current={active ? "page" : undefined}
                    className={`whitespace-nowrap rounded-md px-3 py-1.5 text-[13px] ${active ? "bg-card text-text" : "text-muted"}`}>
                {label}
              </Link>
            );
          })}
        </nav>
      </header>
    </>
  );
}

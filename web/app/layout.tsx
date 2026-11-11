import type { Metadata } from "next";
import { Geist, IBM_Plex_Mono } from "next/font/google";
import { Sidebar } from "@/components/Sidebar";
import { getStatus } from "@/lib/snapshot";
import "./globals.css";

const sans = Geist({ subsets: ["latin", "latin-ext"], variable: "--font-geist", display: "swap" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Matchup DNA", template: "%s · Matchup DNA" },
  description: "Pre-match win probabilities for ATP and WTA singles, recorded before play and scored openly.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const status = await getStatus();
  return (
    <html lang="en-GB" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2">
          Skip to content
        </a>
        <Sidebar
          last={status.ok ? status.data.freshness.forecast.last : null}
          staleAfter={status.ok ? status.data.stale_after_hours : 18}
          ok={status.ok && status.data.integrity.ok}
        />
        <div className="lg:pl-[232px]">
          <main id="main" className="mx-auto w-full max-w-[1180px] px-4 pb-16 pt-6 sm:px-8 lg:pt-10">{children}</main>
          <footer className="mx-auto max-w-[1180px] border-t border-border px-4 py-6 text-[12px] text-dim sm:px-8">
            Non-commercial research. Not betting advice. Data: Jeff Sackmann (CC BY-NC-SA 4.0), TennisIsMyLife, TennisData.app,
            ESPN, Flashscore (ITF, Challenger and tour results), TennisExplorer (weekly rankings); prices for research only:
            Valuebetennis (CC BY 4.0). Player photos: WTA and ESPN, used with permission, and
            Wikimedia Commons contributors under the licence credited on each player&apos;s page.
          </footer>
        </div>
      </body>
    </html>
  );
}

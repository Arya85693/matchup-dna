import type { Metadata } from "next";
import Link from "next/link";
import { getHistoryIndex } from "@/lib/snapshot";
import { LocalTime } from "@/components/LocalTime";
import { PlayersBrowser } from "@/components/PlayersBrowser";
import { EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Players" };

export default async function PlayersPage() {
  const index = await getHistoryIndex();
  const latest = index.ok ? index.data.players.reduce((m, p) => (p.last_match > m ? p.last_match : m), "") : null;
  return (
    <>
      <PageHeader
        title="Players"
        description="Every ATP and WTA player with a tour-level match in the past year, rated by Elo from their full match history."
        actions={index.ok ? (
          <p className="text-right text-[12px] text-dim">
            Ratings updated <span className="text-muted"><LocalTime iso={index.data.generated_at} style="datetime" /></span>
            {latest && <><br />Results through <span className="fig text-muted">{latest}</span></>}
          </p>
        ) : undefined}
      />
      {index.ok ? <PlayersBrowser players={index.data.players} />
        : <div className="card"><EmptyState title="Player ratings are not available right now">{index.detail} The forecasts are unaffected; ratings return with the next update.</EmptyState></div>}
      <section aria-label="About rankings" className="mt-10 grid gap-2 border-t border-border pt-6 text-[13px] text-muted lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-8">
        <h2 className="text-[13px] font-medium text-text">Elo, not rankings</h2>
        <div className="grid max-w-[78ch] gap-2">
          <p>
            Players here are ordered by Matchup DNA&apos;s Elo rating; official rankings are not shown. Rankings were the
            benchmark the earlier models had to beat. In a post-hoc check over 2021 to October 2026, the Phase 4 model&apos;s
            probabilities beat a rankings-only model in every period (log loss <span className="fig text-text">0.6101</span> against{" "}
            <span className="fig text-text">0.6282</span> pooled). When the model and the higher-ranked player disagreed, the
            model was right <span className="fig text-text">55.9%</span> of the time over 4,578 matches, but that edge fell to{" "}
            <span className="fig text-text">51.9%</span> in the most recent months.
          </p>
          <p className="text-dim">Post-hoc and not pre-registered: descriptive only. Ranking remains one of the model&apos;s inputs. <Link href="/lab#benchmarks" className="link">Model Lab</Link></p>
        </div>
      </section>
      <section aria-label="Who is listed" className="mt-6 grid gap-2 border-t border-border pt-6 text-[13px] text-muted lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-8">
        <h2 className="text-[13px] font-medium text-text">Who is listed</h2>
        <p className="max-w-[78ch]">
          Active players only: a tour-level match in the last 12 months and no announced retirement. Retired players still
          count in the history: their matches shape everyone&apos;s ratings, appear in other players&apos; results and stay in
          every backtest.
        </p>
      </section>
    </>
  );
}

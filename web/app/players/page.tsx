import type { Metadata } from "next";
import Link from "next/link";
import { getHistoryIndex, getItfHistoryIndex } from "@/lib/snapshot";
import { CircuitTabs } from "@/components/CircuitTabs";
import { LocalTime } from "@/components/LocalTime";
import { PlayersBrowser } from "@/components/PlayersBrowser";
import { EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Players" };

export default async function PlayersPage() {
  const [index, itf] = await Promise.all([getHistoryIndex(), getItfHistoryIndex()]);
  const latest = index.ok ? index.data.players.reduce((m, p) => (p.last_match > m ? p.last_match : m), "") : null;
  return (
    <>
      <PageHeader
        title="Players"
        description="Two boards: main-tour ATP and WTA players, and ITF players. Each is rated its own way, so the two are never mixed."
        actions={index.ok ? (
          <p className="text-right text-[12px] text-dim">
            Main-tour ratings updated <span className="text-muted"><LocalTime iso={index.data.generated_at} style="datetime" /></span>
            {latest && <><br />Results through <span className="fig text-muted">{latest}</span></>}
          </p>
        ) : undefined}
      />
      <CircuitTabs label="Board"
        main={<>
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
        </>}
        itf={<>
          {itf.ok ? <PlayersBrowser players={itf.data.players} base="/players/itf" circuit="itf" param="itf_tour" />
            : <div className="card"><EmptyState title="The ITF board is not available yet">{itf.detail} The ITF forecasts and test results are on the ITF page.</EmptyState></div>}
          {itf.ok && <p className="mt-3 text-[12px] text-dim">ITF ratings updated <LocalTime iso={itf.data.generated_at} style="datetime" />.</p>}
          <section aria-label="About the ITF board" className="mt-10 grid gap-2 border-t border-border pt-6 text-[13px] text-muted lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-8">
            <h2 className="text-[13px] font-medium text-text">A different rating</h2>
            <div className="grid max-w-[78ch] gap-2">
              <p>
                The ITF board&apos;s Elo is the one the ITF model uses: one rating over every level a player has played, from
                ITF events to the Grand Slams, that moves faster while a player is new. It is not on the same scale as the
                main-tour Elo, so a player listed on both boards has two different numbers.
              </p>
              <p>
                Listed: the 500 highest-rated men and the 500 highest-rated women with at least five ITF main-draw matches in
                the last 52 weeks. Season records and head to heads count matches at every level.
              </p>
              <p className="text-dim">Display only: recomputed once a day and never a forecast input. <Link href="/itf" className="link">ITF forecasts</Link></p>
            </div>
          </section>
        </>}
      />
    </>
  );
}

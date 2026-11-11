import type { Metadata } from "next";
import Link from "next/link";
import { getIndex, getItf } from "@/lib/snapshot";
import { CircuitTabs } from "@/components/CircuitTabs";
import { ItfRecent, ItfUpcoming } from "@/components/ItfLists";
import { MatchList } from "@/components/MatchList";
import { Card, EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 60;          // results arrive between scheduled publishes; show them within a minute
export const metadata: Metadata = { title: "Matches" };

export default async function MatchesPage() {
  const [index, itf] = await Promise.all([getIndex(), getItf()]);
  return (
    <>
      <PageHeader title="Matches" description="Main tour (ATP and WTA): tournament-start forecasts, with the round-aware update on each match page. ITF (ITF Men and ITF Women): the ITF model's forecasts." />
      <CircuitTabs
        main={index.ok ? <MatchList matches={index.data.matches} /> : <div className="card"><EmptyState title="Match data could not be loaded">{index.detail}</EmptyState></div>}
        itf={itf.ok ? (
          <>
            <Card title="Upcoming ITF matches" padded={false} action={<Link href="/itf" className="link text-[12px]">ITF record and tests</Link>}>
              <ItfUpcoming rows={itf.data.upcoming} limit={150} />
            </Card>
            <Card title="Recent ITF results" className="mt-6" padded={false}><ItfRecent rows={itf.data.recent} /></Card>
          </>
        ) : <div className="card"><EmptyState title="ITF forecasts are not published yet">{itf.detail}</EmptyState></div>}
      />
    </>
  );
}

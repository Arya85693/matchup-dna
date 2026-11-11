import type { Metadata } from "next";
import { getArchive, getItf } from "@/lib/snapshot";
import { ArchiveView } from "@/components/archive/ArchiveView";
import { CircuitTabs } from "@/components/CircuitTabs";
import { ItfArchive } from "@/components/ItfArchive";
import { EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Forecast Archive" };

export default async function ArchivePage() {
  const [archive, itf] = await Promise.all([getArchive(), getItf()]);
  return (
    <>
      <PageHeader title="Forecast Archive" description="Every forecast ever issued, locked before its match and kept unchanged: main-tour forecasts (tournament start and round-aware) and ITF forecasts (ITF M1). Inspect any record for its inputs and hashes." />
      <CircuitTabs
        main={archive.ok ? <ArchiveView entries={archive.data.entries} /> : <div className="card"><EmptyState title="The archive could not be loaded">{archive.detail}</EmptyState></div>}
        itf={itf.ok ? <ItfArchive rows={itf.data.archive} /> : <div className="card"><EmptyState title="ITF forecasts are not published yet">{itf.detail}</EmptyState></div>}
      />
    </>
  );
}

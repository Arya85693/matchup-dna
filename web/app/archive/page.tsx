import type { Metadata } from "next";
import { getArchive } from "@/lib/snapshot";
import { ArchiveTable } from "@/components/Archive";
import { EmptyState, PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Forecast Archive" };

export default async function ArchivePage() {
  const archive = await getArchive();
  return (
    <>
      <PageHeader title="Forecast Archive" description="Every forecast ever issued, with its timestamp, model version, outcome and ledger position." />
      {archive.ok ? <ArchiveTable entries={archive.data.entries} /> : <div className="card"><EmptyState title="The archive could not be loaded">{archive.detail}</EmptyState></div>}
    </>
  );
}

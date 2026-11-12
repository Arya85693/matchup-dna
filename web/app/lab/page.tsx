import type { Metadata } from "next";
import { HISTORICAL, MARKET } from "@/lib/research";
import { getArchive, getItf, getItfArchive, getModels, getTrackRecord } from "@/lib/snapshot";
import { ItfSchema } from "@/lib/contract";
import { toLedgerEntry } from "@/lib/ledger";
import itfResearch from "@/content/research/itf.json";
import { LabShell } from "@/components/lab/LabShell";
import { PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Model Lab" };

export default async function LabPage() {
  const [record, models, archive, itf, itfArchive] = await Promise.all([getTrackRecord(), getModels(), getArchive(), getItf(), getItfArchive()]);
  const research = itf.ok ? itf.data.research : ItfSchema.shape.research.parse(itfResearch);
  return (
    <>
      <PageHeader title="Model Lab" description="How good the forecasts are, and how strong the evidence is behind each claim." />
      <LabShell record={record.ok ? record.data : null} archive={archive.ok ? archive.data.entries.map(toLedgerEntry) : []}
                historical={HISTORICAL} market={MARKET} models={models.ok ? models.data : null}
                itfResearch={research} itfRecord={itf.ok ? itf.data.record : null}
                itfLive={{
                  entries: itfArchive.ok ? itfArchive.data.entries.map(toLedgerEntry) : [],
                  frozenAt: itf.ok ? itf.data.protocol.frozen_at : null,
                  generatedAt: itfArchive.ok ? itfArchive.data.generated_at : null,
                }} />
    </>
  );
}

import type { Metadata } from "next";
import { HISTORICAL, MARKET } from "@/lib/research";
import { getArchive, getModels, getTrackRecord } from "@/lib/snapshot";
import { LabShell } from "@/components/lab/LabShell";
import { PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Model Lab" };

export default async function LabPage() {
  const [record, models, archive] = await Promise.all([getTrackRecord(), getModels(), getArchive()]);
  return (
    <>
      <PageHeader title="Model Lab" description="How good the forecasts are, and how strong the evidence is behind each claim." />
      <LabShell record={record.ok ? record.data : null} archive={archive.ok ? archive.data.entries : []}
                historical={HISTORICAL} market={MARKET} models={models.ok ? models.data : null} />
    </>
  );
}

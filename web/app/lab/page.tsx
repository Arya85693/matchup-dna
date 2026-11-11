import type { Metadata } from "next";
import { HISTORICAL, MARKET } from "@/lib/research";
import { getArchive, getItf, getModels, getTrackRecord } from "@/lib/snapshot";
import { ItfSchema } from "@/lib/contract";
import itfResearch from "@/content/research/itf.json";
import { LabShell } from "@/components/lab/LabShell";
import { PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Model Lab" };

export default async function LabPage() {
  const [record, models, archive, itf] = await Promise.all([getTrackRecord(), getModels(), getArchive(), getItf()]);
  const research = itf.ok ? itf.data.research : ItfSchema.shape.research.parse(itfResearch);
  return (
    <>
      <PageHeader title="Model Lab" description="How good the forecasts are, and how strong the evidence is behind each claim." />
      <LabShell record={record.ok ? record.data : null} archive={archive.ok ? archive.data.entries : []}
                historical={HISTORICAL} market={MARKET} models={models.ok ? models.data : null}
                itfResearch={research} itfRecord={itf.ok ? itf.data.record : null} />
    </>
  );
}

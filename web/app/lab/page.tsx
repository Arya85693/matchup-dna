import type { Metadata } from "next";
import { HISTORICAL, MARKET } from "@/lib/research";
import { getModels, getTrackRecord } from "@/lib/snapshot";
import { Lab } from "@/components/Lab";
import { PageHeader } from "@/components/ui";

export const revalidate = 300;
export const metadata: Metadata = { title: "Model Lab" };

export default async function LabPage() {
  const [record, models] = await Promise.all([getTrackRecord(), getModels()]);
  return (
    <>
      <PageHeader title="Model Lab" description="How the forecasts perform: the live record, earlier tests, calibration and the betting-market benchmark." />
      <Lab record={record.ok ? record.data : null} historical={HISTORICAL} market={MARKET} models={models.ok ? models.data : null} />
    </>
  );
}

import type { Metadata } from "next";
import { getItfHistoryIndex, getItfHistoryPlayer } from "@/lib/snapshot";
import { ComparePage } from "@/components/players/ComparePage";

export const metadata: Metadata = { title: "Compare ITF players" };

type Props = { searchParams: Promise<{ a?: string; b?: string; tour?: string }> };

export default async function CompareItf({ searchParams }: Props) {
  return <ComparePage query={await searchParams} index={getItfHistoryIndex} player={getItfHistoryPlayer} base="/players/itf" board="/players?circuit=itf" circuit="itf" />;
}

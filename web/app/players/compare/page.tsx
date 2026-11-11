import type { Metadata } from "next";
import { getHistoryIndex, getHistoryPlayer } from "@/lib/snapshot";
import { ComparePage } from "@/components/players/ComparePage";

export const metadata: Metadata = { title: "Compare players" };

type Props = { searchParams: Promise<{ a?: string; b?: string; tour?: string }> };

export default async function Compare({ searchParams }: Props) {
  return <ComparePage query={await searchParams} index={getHistoryIndex} player={getHistoryPlayer} base="/players" board="/players" circuit="main" />;
}

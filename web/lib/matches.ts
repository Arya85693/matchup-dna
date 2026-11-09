import type { MatchSummary } from "./contract";

/** Matches grouped by tournament edition, keeping their order. Shared by server and client components. */
export function groupByEdition(matches: MatchSummary[]): MatchSummary[][] {
  const groups = new Map<string, MatchSummary[]>();
  for (const m of matches) groups.set(m.edition.uid, [...(groups.get(m.edition.uid) ?? []), m]);
  return [...groups.values()];
}

"use client";

import { useRouter } from "next/navigation";

/** Pick a second player of the same tour and open the comparison. */
export function ComparePicker({ id, options }: { id: number; options: { id: number; name: string }[] }) {
  const router = useRouter();
  return (
    <label className="flex items-center gap-2 text-[13px] text-muted">
      Compare with
      <select id="compare-with" defaultValue="" onChange={(e) => { if (e.target.value) router.push(`/players/compare?a=${id}&b=${e.target.value}`); }}
              className="max-w-[220px] rounded-md border border-border bg-card px-2 py-1.5 text-[13px] text-text">
        <option value="" disabled>Choose a player</option>
        {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
    </label>
  );
}

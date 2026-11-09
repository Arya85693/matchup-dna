/** Shown while the player ratings load: the page's real geometry with static placeholders (no shimmer). */
export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading players">
      <div className="pb-8"><div className="h-7 w-32 rounded bg-card" /><div className="mt-2.5 h-4 w-96 max-w-full rounded bg-card" /></div>
      <div className="h-[92px] rounded-lg border border-border bg-card/50" />
      <div className="mt-4 overflow-hidden rounded-lg border border-border">
        <div className="h-9 border-b border-border bg-card" />
        {Array.from({ length: 12 }, (_, i) => (
          <div key={i} className="flex items-center gap-4 border-b border-border px-4 py-3">
            <div className="h-3 w-6 rounded bg-card" /><div className="h-3 w-40 rounded bg-card" /><div className="ml-auto h-3 w-10 rounded bg-card" /><div className="h-3 w-16 rounded bg-card" />
          </div>
        ))}
      </div>
    </div>
  );
}

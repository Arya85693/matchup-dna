"use client";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="card mt-6 px-6 py-12 text-center">
      <h1 className="text-[18px] font-semibold">This page failed to load</h1>
      <p className="mt-2 text-muted">Stored forecasts are not affected.</p>
      <div className="mt-5 flex justify-center gap-4 text-[13px]">
        <button onClick={reset} className="link">Try again</button>
        <a href="/status" className="link">Data status</a>
      </div>
    </div>
  );
}

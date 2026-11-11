"use client";

import { useEffect, useState } from "react";
import { Segmented } from "./lab/parts";

/** Main tour | ITF, used on the Players, Matches and Archive pages. The two have different models, ratings and
 * records, so they are shown one at a time, never mixed. The open tab is kept in the address (`?circuit=itf`), so a
 * link or the back button returns to it. */
export function CircuitTabs({ main, itf, label = "Circuit" }: { main: React.ReactNode; itf: React.ReactNode; label?: string }) {
  const [view, setView] = useState<"main" | "itf">("main");
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("circuit") === "itf") setView("itf");
  }, []);
  const choose = (v: "main" | "itf") => {
    setView(v);
    const q = new URLSearchParams(window.location.search);
    if (v === "itf") q.set("circuit", "itf"); else q.delete("circuit");
    const rest = q.toString();
    window.history.replaceState(null, "", rest ? `?${rest}` : window.location.pathname);
  };
  return (
    <>
      <div className="mb-6">
        <Segmented label={label} value={view} onChange={choose} options={[["main", "Main tour"], ["itf", "ITF"]]} />
      </div>
      {/* Only the open tab is on the page: one search box, one table, no hidden copies for screen readers to find. */}
      <div key={view}>{view === "main" ? main : itf}</div>
    </>
  );
}

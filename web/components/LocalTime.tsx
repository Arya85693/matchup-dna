"use client";

import { useEffect, useState } from "react";

type Style = "time" | "date" | "datetime" | "weekday";

const OPTIONS: Record<Style, Intl.DateTimeFormatOptions> = {
  time: { hour: "2-digit", minute: "2-digit", hourCycle: "h23" },
  date: { day: "numeric", month: "short", year: "numeric" },
  datetime: { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" },
  weekday: { weekday: "short", day: "numeric", month: "short" },
};

function format(iso: string, style: Style, timeZone?: string) {
  return new Intl.DateTimeFormat("en-GB", { ...OPTIONS[style], timeZone }).format(new Date(iso));
}

/**
 * A time in the viewer's time zone, with the exact UTC instant on hover. The server renders UTC (it cannot know
 * the viewer's zone); the browser replaces it after the first paint.
 */
export function LocalTime({ iso, style = "time", showZone = false }: { iso: string; style?: Style; showZone?: boolean }) {
  const [local, setLocal] = useState<string | null>(null);
  useEffect(() => setLocal(format(iso, style)), [iso, style]);
  const utc = `${format(iso, "datetime", "UTC")} UTC`;
  return (
    <time dateTime={iso} title={utc} suppressHydrationWarning>
      {local ?? format(iso, style, "UTC")}
      {showZone && !local ? " UTC" : ""}
    </time>
  );
}

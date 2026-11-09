"use client";

import { useState } from "react";

/**
 * A player's photo (the official ATP or WTA headshot, else a Wikimedia Commons photo, else ESPN's; only for verified
 * identities), or their initials when there is no photo or it fails to load. Lazy-loaded and sent without a referrer.
 */
export function PlayerPhoto({ name, src, size = 40, className = "" }: { name: string; src: string | null; size?: number; className?: string }) {
  const [failed, setFailed] = useState(false);
  const initials = name.split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const box = { width: size, height: size };
  if (!src || failed) {
    return (
      <span aria-hidden="true" style={box}
            className={`inline-flex shrink-0 items-center justify-center rounded-full border border-border-strong bg-card-hover font-medium text-muted ${className}`}>
        <span style={{ fontSize: Math.max(10, size * 0.36) }}>{initials}</span>
      </span>
    );
  }
  // Wikimedia sets tracking cookies on its images; it allows anonymous (credential-free) loading, which drops them.
  // Other hosts may not send CORS headers, so they load normally.
  const anonymous = /^https:\/\/(thumb|upload)\.wikimedia\.org\//.test(src) ? "anonymous" : undefined;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- remote headshots, linked rather than proxied
    <img src={src} alt={name} width={size} height={size} loading="lazy" decoding="async" referrerPolicy="no-referrer" crossOrigin={anonymous} onError={() => setFailed(true)}
         style={box} className={`shrink-0 rounded-full border border-border bg-card-hover object-cover object-top ${className}`} />
  );
}

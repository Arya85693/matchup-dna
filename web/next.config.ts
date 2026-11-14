import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The publisher's Python lives in web/publisher; nothing there is part of the Next.js build.
  outputFileTracingExcludes: { "*": ["publisher/**", ".data/**"] },
  // Earlier page addresses, kept working after the redesign.
  async redirects() {
    return [
      // The first site's research pages were folded into the Model Lab; /research is now the papers tab.
      { source: "/research/:old(market|historical)", destination: "/lab", permanent: false },
      // The myth-check article moved to the Research tab as a working paper (November 2026).
      { source: "/methodology/big-matches", destination: "/research/big-matches", permanent: true },
      // The ITF page was folded into Matches (ITF), the Model Lab and the Archive (November 2026).
      { source: "/itf", destination: "/matches?circuit=itf", permanent: false },
    ];
  },
};

export default config;

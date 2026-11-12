import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The publisher's Python lives in web/publisher; nothing there is part of the Next.js build.
  outputFileTracingExcludes: { "*": ["publisher/**", ".data/**"] },
  // Earlier page addresses, kept working after the redesign.
  async redirects() {
    return [
      { source: "/research", destination: "/lab", permanent: false },
      { source: "/research/:path*", destination: "/lab", permanent: false },
      // The ITF page was folded into Matches (ITF), the Model Lab and the Archive (November 2026).
      { source: "/itf", destination: "/matches?circuit=itf", permanent: false },
    ];
  },
};

export default config;

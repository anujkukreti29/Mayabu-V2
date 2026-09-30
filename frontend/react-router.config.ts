import type { Config } from "@react-router/dev/config";

export default {
  ssr: true,

  future: {
    unstable_optimizeDeps: true,
  },

  // Category landings are SSR'd at request time against live catalog data.
  // Do not prerender them into a stale static snapshot.
  prerender: [
    "/",
    "/about",
    "/platforms",
    "/how-it-works",
    "/contact",
    "/privacy",
    "/terms",
    "/disclaimer",
  ],
} satisfies Config;

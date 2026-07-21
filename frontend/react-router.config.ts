import type { Config } from "@react-router/dev/config";

export default {
  ssr: true,
  prerender: [
    "/",
    "/about",
    "/platforms",
    "/how-it-works",
    "/contact",
    "/privacy",
    "/terms",
    "/disclaimer",
    "/laptops",
    "/mobile-phones",
  ],
} satisfies Config;

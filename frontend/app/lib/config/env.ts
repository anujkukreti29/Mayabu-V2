import { z } from "zod";

const booleanFlag = z
  .enum(["true", "false"])
  .default("false")
  .transform((value) => value === "true");

const schema = z.object({
  VITE_API_BASE_URL: z.string().url().default("http://127.0.0.1:8000"),
  VITE_SITE_URL: z.string().url().default("http://localhost:5173"),
  VITE_APP_ENV: z.enum(["development", "staging", "production", "test"]).default("development"),
  VITE_RENDER_MODE: z.enum(["ssr", "spa"]).default("ssr"),
  VITE_CANONICAL_HOST: z.string().url().optional(),
  VITE_ENABLE_AUTH: booleanFlag,
  VITE_ENABLE_TRACKER: booleanFlag,
  VITE_ENABLE_ASSISTANT: booleanFlag,
  VITE_ENABLE_ADMIN: booleanFlag,
  VITE_ENABLE_DEALS: booleanFlag,
  VITE_ENABLE_ANALYTICS: booleanFlag,
  VITE_ENABLE_COOKIE_BANNER: booleanFlag,
});

const rawEnvironment = import.meta.env;
const parsed = schema.safeParse(rawEnvironment);
if (!parsed.success) {
  throw new Error(`Invalid Mayabu frontend configuration: ${parsed.error.message}`);
}

if (parsed.data.VITE_APP_ENV === "production") {
  const missing = ["VITE_API_BASE_URL", "VITE_SITE_URL"].filter(
    (key) => !rawEnvironment[key as keyof ImportMetaEnv],
  );
  if (missing.length > 0) {
    throw new Error(`Missing production frontend configuration: ${missing.join(", ")}`);
  }
}

export const env = Object.freeze({
  apiBaseUrl: parsed.data.VITE_API_BASE_URL.replace(/\/$/, ""),
  siteUrl: (parsed.data.VITE_CANONICAL_HOST ?? parsed.data.VITE_SITE_URL).replace(/\/$/, ""),
  appEnv: parsed.data.VITE_APP_ENV,
  renderMode: parsed.data.VITE_RENDER_MODE,
  features: Object.freeze({
    auth: parsed.data.VITE_ENABLE_AUTH,
    tracker: parsed.data.VITE_ENABLE_TRACKER,
    assistant: parsed.data.VITE_ENABLE_ASSISTANT,
    admin: parsed.data.VITE_ENABLE_ADMIN,
    deals: parsed.data.VITE_ENABLE_DEALS,
    analytics: parsed.data.VITE_ENABLE_ANALYTICS,
    cookieBanner: parsed.data.VITE_ENABLE_COOKIE_BANNER,
  }),
});

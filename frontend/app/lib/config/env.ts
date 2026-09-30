import { z } from "zod";

const booleanFlag = z
  .enum(["true", "false"])
  .default("false")
  .transform((value) => value === "true");

const schema = z.object({
  VITE_API_BASE_URL: z.string().default("http://127.0.0.1:8000"),
  VITE_API_SERVER_URL: z.string().optional(),
  VITE_API_BROWSER_MODE: z.enum(["same-origin", "absolute"]).optional(),
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

function stripTrailingSlash(value: string): string {
  return value.replace(/\/$/, "");
}

function asAbsoluteApiUrl(value: string, label: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`${label} must be a non-empty absolute Mayabu API URL.`);
  }
  if (trimmed.startsWith("/")) {
    throw new Error(`${label} must be absolute (got a path).`);
  }
  try {
    const parsedUrl = new URL(trimmed);
    if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") {
      throw new Error("unsupported protocol");
    }
    return stripTrailingSlash(
      parsedUrl.origin + (parsedUrl.pathname === "/" ? "" : parsedUrl.pathname),
    );
  } catch {
    throw new Error(`Invalid Mayabu API URL for ${label}: ${trimmed}`);
  }
}

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
  const site = stripTrailingSlash(
    String(rawEnvironment.VITE_CANONICAL_HOST || rawEnvironment.VITE_SITE_URL || ""),
  );
  if (!site.startsWith("https://")) {
    throw new Error(
      "Production VITE_SITE_URL / VITE_CANONICAL_HOST must be an https:// public base URL.",
    );
  }
}

const apiServerUrl = asAbsoluteApiUrl(
  parsed.data.VITE_API_SERVER_URL || parsed.data.VITE_API_BASE_URL || "http://127.0.0.1:8000",
  "API server URL",
);

const browserMode =
  parsed.data.VITE_API_BROWSER_MODE ??
  (parsed.data.VITE_APP_ENV === "development" ? "same-origin" : "absolute");

const apiBrowserUrl =
  browserMode === "same-origin"
    ? ""
    : asAbsoluteApiUrl(parsed.data.VITE_API_BASE_URL || apiServerUrl, "API browser URL");

/**
 * Resolve the API origin for the current runtime.
 * - SSR / Node: always the internal absolute server URL
 * - Browser (dev default): same-origin "" so Vite proxies /api → backend
 * - Browser (test/prod absolute): configured public API origin
 */
export function resolveApiBaseUrl(): string {
  if (import.meta.env.SSR || typeof window === "undefined") {
    return apiServerUrl;
  }
  return apiBrowserUrl;
}

export const env = Object.freeze({
  apiServerUrl,
  apiBrowserUrl,
  apiBaseUrl: apiBrowserUrl || apiServerUrl,
  browserMode,
  siteUrl: stripTrailingSlash(parsed.data.VITE_CANONICAL_HOST ?? parsed.data.VITE_SITE_URL),
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

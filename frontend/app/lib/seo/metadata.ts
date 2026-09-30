/** Centralized canonical URL + page metadata helpers (SEO V2). */

import { env } from "~/lib/config/env";
import { normalizeProductImageUrl } from "~/lib/media/product-image-url";

const DEFAULT_OG_IMAGE = "/og-default.svg";

/** Strip trailing slash (except root) and drop query/hash for canonical paths. */
export function canonicalizePath(path: string): string {
  let value = (path || "/").trim();
  if (!value.startsWith("/")) value = `/${value}`;
  const noHash = value.split("#")[0] ?? value;
  const noQuery = noHash.split("?")[0] ?? noHash;
  if (noQuery.length > 1 && noQuery.endsWith("/")) {
    return noQuery.slice(0, -1);
  }
  return noQuery || "/";
}

export function absoluteUrl(path: string): string {
  const clean = canonicalizePath(path);
  return new URL(clean, `${env.siteUrl}/`).toString();
}

export function sanitizeMetaText(value: string, maxLength = 120): string {
  return value
    .replace(/[<>\n\r]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLength);
}

/** Non-production staging must not be indexed. Development keeps intended robots for local QA. */
export function defaultRobots(preferred = "index, follow"): string {
  if (env.appEnv === "staging") return "noindex, nofollow";
  return preferred;
}

export function isIndexingEnabled(): boolean {
  return env.appEnv === "production";
}

export function shouldEmitNoindexHeader(): boolean {
  return env.appEnv !== "production";
}

export function safeSocialImageUrl(image?: string | null): string {
  const normalized = normalizeProductImageUrl(image);
  if (normalized) return normalized;
  return absoluteUrl(DEFAULT_OG_IMAGE);
}

export function pageMeta({
  title,
  description,
  path,
  robots,
  image,
  ogType = "website",
}: {
  title: string;
  description: string;
  path: string;
  robots?: string;
  image?: string | null;
  ogType?: "website" | "product";
}) {
  const canonicalPath = canonicalizePath(path);
  const canonical = absoluteUrl(canonicalPath);
  const safeTitle = sanitizeMetaText(title, 70);
  const safeDescription = sanitizeMetaText(description, 165);
  const robotsValue = defaultRobots(robots ?? "index, follow");
  const ogImage = safeSocialImageUrl(image);

  return [
    { title: safeTitle },
    { name: "description", content: safeDescription },
    { name: "robots", content: robotsValue },
    { tagName: "link", rel: "canonical", href: canonical },
    { property: "og:title", content: safeTitle },
    { property: "og:description", content: safeDescription },
    { property: "og:url", content: canonical },
    { property: "og:type", content: ogType },
    { property: "og:image", content: ogImage },
    { name: "twitter:card", content: "summary_large_image" },
    { name: "twitter:title", content: safeTitle },
    { name: "twitter:description", content: safeDescription },
    { name: "twitter:image", content: ogImage },
  ];
}

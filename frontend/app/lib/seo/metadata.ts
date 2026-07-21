import { env } from "~/lib/config/env";

export function absoluteUrl(path: string): string {
  return new URL(path, `${env.siteUrl}/`).toString();
}

export function sanitizeMetaText(value: string, maxLength = 120): string {
  return value
    .replace(/[<>\n\r]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLength);
}

export function pageMeta({
  title,
  description,
  path,
  robots = "index, follow",
  image = "/og-default.svg",
  ogType = "website",
}: {
  title: string;
  description: string;
  path: string;
  robots?: string;
  image?: string;
  ogType?: "website" | "product";
}) {
  const canonical = absoluteUrl(path);
  const safeTitle = sanitizeMetaText(title, 70);
  const safeDescription = sanitizeMetaText(description, 165);
  return [
    { title: safeTitle },
    { name: "description", content: safeDescription },
    { name: "robots", content: robots },
    { tagName: "link", rel: "canonical", href: canonical },
    { property: "og:title", content: safeTitle },
    { property: "og:description", content: safeDescription },
    { property: "og:url", content: canonical },
    { property: "og:type", content: ogType },
    { property: "og:image", content: absoluteUrl(image) },
    { name: "twitter:card", content: "summary_large_image" },
  ];
}

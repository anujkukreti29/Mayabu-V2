import { env } from "~/lib/config/env";
export function loader() {
  const body = [
    `User-agent: *`,
    `Allow: /`,
    `Disallow: /admin`,
    `Disallow: /account`,
    `Disallow: /assistant`,
    `Sitemap: ${env.siteUrl}/sitemap.xml`,
    ``,
  ].join("\n");
  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}

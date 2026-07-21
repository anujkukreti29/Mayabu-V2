import { env } from "~/lib/config/env";
import { staticIndexablePaths } from "~/lib/navigation/routes";

export function loader() {
  const urls = staticIndexablePaths
    .map((path) => `<url><loc>${new URL(path, `${env.siteUrl}/`).toString()}</loc></url>`)
    .join("");
  const xml = `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>`;
  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}

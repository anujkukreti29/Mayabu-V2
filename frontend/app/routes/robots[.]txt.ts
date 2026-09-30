import { env } from "~/lib/config/env";
import { absoluteUrl } from "~/lib/seo/metadata";

export function loader() {
  const lines: string[] = [`User-agent: *`];

  if (env.appEnv !== "production") {
    // Staging/dev must not be indexed.
    lines.push(`Disallow: /`);
  } else {
    lines.push(`Allow: /`);
    lines.push(`Disallow: /admin`);
    lines.push(`Disallow: /account`);
    lines.push(`Disallow: /wishlist`);
    lines.push(`Disallow: /assistant`);
    lines.push(`Disallow: /search`);
    lines.push(`Disallow: /compare`);
    lines.push(`Disallow: /sign-in`);
    lines.push(`Disallow: /login`);
    lines.push(`Disallow: /signup`);
    lines.push(`Disallow: /forgot-password`);
    lines.push(`Disallow: /reset-password`);
    lines.push(`Disallow: /verify-email`);
    lines.push(`Disallow: /tracker`);
    lines.push(`Disallow: /api`);
    lines.push(`Sitemap: ${absoluteUrl("/sitemap.xml")}`);
  }

  lines.push(``);
  const headers: Record<string, string> = {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": env.appEnv === "production" ? "public, max-age=3600" : "no-store",
  };
  if (env.appEnv !== "production") {
    headers["X-Robots-Tag"] = "noindex, nofollow";
  }
  return new Response(lines.join("\n"), { headers });
}

import { readFile } from "node:fs/promises";

const pages = [
  ["build/client/index.html", "Find the best place to buy electronics in India"],
  ["build/client/about/index.html", "About Mayabu"],
  ["build/client/platforms/index.html", "Supported ecommerce platforms"],
  ["build/client/how-it-works/index.html", "How Mayabu helps you compare before buying"],
  ["build/client/laptops/index.html", "Compare laptops by exact model"],
  ["build/client/mobile-phones/index.html", "Compare mobile phones by exact variant"],
];
for (const [file, heading] of pages) {
  const html = await readFile(file, "utf8");
  const checks = [
    [/<title>[^<]+<\/title>/, "title"],
    [/<meta[^>]+name="description"[^>]+content="[^"]+"/, "description"],
    [/<link[^>]+rel="canonical"[^>]+href="[^"]+"/, "canonical"],
    [/<meta[^>]+name="robots"[^>]+content="index, follow"/, "robots"],
    [/<main[\s>]/, "main"],
    [new RegExp(heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"), "H1 content"],
  ];
  for (const [pattern, label] of checks)
    if (!pattern.test(html)) throw new Error(`${file} is missing ${label}`);
}
const sitemapSource = await readFile("app/routes/sitemap[.]xml.ts", "utf8");
for (const forbidden of ["/search", "/compare", "/admin", "/account", "/verification"]) {
  if (sitemapSource.includes(`\"${forbidden}\"`))
    throw new Error(`Sitemap must exclude ${forbidden}`);
}
console.log(`SEO verification passed for ${pages.length} prerendered pages.`);

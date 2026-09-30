/**
 * Bounded local SEO crawl for Mayabu SSR.
 * Usage: node scripts/seo-crawl.mjs
 */
import { chromium } from "@playwright/test";

const BASE = process.env.MAYABU_QA_BASE || "http://127.0.0.1:5173";

const SEEDS = [
  "/",
  "/laptops",
  "/smartphones",
  "/televisions",
  "/refrigerators",
  "/washing-machines",
  "/tws",
  "/headphones",
  "/cameras",
  "/search?q=asus",
  "/compare",
  "/sign-in",
  "/wishlist",
  "/robots.txt",
  "/sitemap.xml",
  "/sitemaps/static.xml",
  "/sitemaps/categories.xml",
];

const browser = await chromium.launch();
const page = await browser.newPage();
const rows = [];

for (const path of SEEDS) {
  const url = `${BASE}${path}`;
  const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  const status = response?.status() ?? 0;
  let title = "";
  let robots = "";
  let canonical = "";
  let h1 = "";
  if (!path.endsWith(".xml") && path !== "/robots.txt") {
    title = await page.title();
    robots = await page
      .locator('meta[name="robots"]')
      .getAttribute("content")
      .catch(() => "");
    canonical = await page
      .locator('link[rel="canonical"]')
      .getAttribute("href")
      .catch(() => "");
    h1 = await page
      .locator("h1")
      .first()
      .innerText()
      .catch(() => "");
  } else {
    const text = await page.content();
    title = path;
    robots =
      text.includes("Disallow") || text.includes("<urlset") || text.includes("<sitemapindex")
        ? "document"
        : "";
  }
  rows.push({ path, status, title, robots, canonical, h1: h1.slice(0, 80) });
  console.log(
    `${status}\t${path}\trobots=${robots || "-"}\tcanon=${canonical || "-"}\th1=${(h1 || "-").slice(0, 40)}`,
  );
}

await browser.close();

const bad = rows.filter((row) => row.status >= 500);
if (bad.length) {
  console.error("SEO crawl found server errors:", bad);
  process.exit(1);
}
console.log(`SEO crawl complete: ${rows.length} URLs`);

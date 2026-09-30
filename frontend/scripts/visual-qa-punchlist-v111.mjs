/**
 * Punch-list V1.1.1 visual QA: compare dock collision + best_price consistency.
 * Requires FE at http://127.0.0.1:5173 and API at http://127.0.0.1:8000
 */
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const BASE = process.env.MAYABU_FE_URL || "http://127.0.0.1:5173";
const API = process.env.MAYABU_API_URL || "http://127.0.0.1:8000";
const OUT = path.resolve("visual-qa-punchlist-v111");

const viewports = [
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "1366", width: 1366, height: 768 },
  { name: "1920", width: 1920, height: 1080 },
];

const TUF_ID = "1211b369-3b40-474c-b4f2-6847f1e6dfc8";

async function searchIds(query, limit = 4) {
  const res = await fetch(`${API}/api/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!res.ok) return [];
  const body = await res.json();
  return (body?.results ?? []).map((item) => item.id).filter(Boolean);
}

async function productPath(id) {
  const res = await fetch(`${API}/api/products/${id}`);
  if (!res.ok) return null;
  const body = await res.json();
  const title = String(body?.product?.title || "product")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);
  return `/products/${id}/${title}`;
}

const laptopIds = await searchIds("asus", 4);
const tufPath = (await productPath(TUF_ID)) || (laptopIds[0] ? await productPath(laptopIds[0]) : null);
const compare2 = laptopIds.length >= 2 ? `/compare?ids=${laptopIds.slice(0, 2).join(",")}` : "/compare";
const compare4 = laptopIds.length >= 2 ? `/compare?ids=${laptopIds.slice(0, 4).join(",")}` : "/compare";

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
let count = 0;
const issues = [];

function overlapReport(boxA, boxB) {
  if (!boxA || !boxB) return null;
  const overlap =
    boxA.x < boxB.x + boxB.width &&
    boxA.x + boxA.width > boxB.x &&
    boxA.y < boxB.y + boxB.height &&
    boxA.y + boxA.height > boxB.y;
  return overlap ? { a: boxA, b: boxB } : null;
}

for (const vp of viewports) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
  for (const route of [
    { id: "compare-2", path: compare2 },
    { id: "compare-4", path: compare4 },
  ]) {
    await page.goto(`${BASE}${route.path}`, { waitUntil: "networkidle", timeout: 45_000 });
    await page.waitForTimeout(250);
    const tray = page.getByRole("complementary", { name: /comparison tray/i });
    const trayCount = await tray.count();
    if (trayCount > 0) {
      issues.push(`${route.id}-${vp.name} dock visible on /compare`);
    }
    const header = page.locator("header").first();
    const productHeader = page.locator("section[aria-labelledby='compare-products-heading']").first();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 2,
    );
    if (overflow && vp.width >= 1366) issues.push(`${route.id}-${vp.name} overflow`);

    for (const pos of ["top", "mid", "bottom"]) {
      if (pos === "mid") await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight * 0.45));
      if (pos === "bottom") await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      if (pos === "top") await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(150);
      const headerBox = await header.boundingBox();
      const productsBox = await productHeader.boundingBox();
      if (trayCount > 0) {
        const dockBox = await tray.first().boundingBox();
        if (overlapReport(headerBox, dockBox) || overlapReport(productsBox, dockBox)) {
          issues.push(`${route.id}-${vp.name}-${pos} dock overlap`);
        }
      }
      await page.screenshot({
        path: path.join(OUT, `${route.id}-${vp.name}-${pos}.png`),
        fullPage: pos === "bottom",
      });
      count += 1;
    }
  }

  if (tufPath) {
    await page.goto(`${BASE}${tufPath}`, { waitUntil: "networkidle", timeout: 45_000 });
    await page.waitForTimeout(250);
    const bodyText = await page.locator("body").innerText();
    if (/Price unavailable/i.test(bodyText) && /₹[\d,]+/.test(bodyText)) {
      issues.push(`pdp-tuf-${vp.name} price unavailable with priced offers`);
    }
    await page.screenshot({ path: path.join(OUT, `pdp-tuf-${vp.name}.png`), fullPage: true });
    count += 1;
  }

  await page.goto(`${BASE}/search?q=asus+tuf+gaming+a15+fa506ncq`, {
    waitUntil: "networkidle",
    timeout: 45_000,
  });
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(OUT, `search-tuf-${vp.name}.png`), fullPage: true });
  count += 1;
  await page.close();
}

await browser.close();
console.log(JSON.stringify({ count, issues, compare2, compare4, tufPath }, null, 2));
if (issues.length) process.exitCode = 1;

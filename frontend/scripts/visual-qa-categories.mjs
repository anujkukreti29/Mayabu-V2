/**
 * Visual QA matrix for category landing pages.
 * Usage: node scripts/visual-qa-categories.mjs
 * Requires FE at 127.0.0.1:5173
 */
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const BASE = process.env.MAYABU_QA_BASE || "http://127.0.0.1:5173";
const OUT = path.resolve("artifacts/visual-qa/categories");
const VIEWPORTS = [
  { name: "390x844", width: 390, height: 844 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1920x1080", width: 1920, height: 1080 },
];
const ROUTES = [
  "/laptops",
  "/smartphones",
  "/televisions",
  "/refrigerators",
  "/washing-machines",
  "/tws",
  "/headphones",
  "/cameras",
];

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
for (const viewport of VIEWPORTS) {
  const page = await browser.newPage({ viewport });
  for (const route of ROUTES) {
    const slug = route.replace(/^\//, "");
    await page.goto(`${BASE}${route}`, { waitUntil: "networkidle", timeout: 60000 });
    const file = path.join(OUT, `${slug}-${viewport.name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    console.log(`wrote ${file}`);
  }
  await page.close();
}
await browser.close();
console.log(`Category visual QA complete: ${ROUTES.length} routes × ${VIEWPORTS.length} viewports`);

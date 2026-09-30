/**
 * UI/UX V1 visual QA — capture priority pages at key viewports.
 * Requires FE at http://127.0.0.1:5173
 */
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const BASE = process.env.MAYABU_FE_URL || "http://127.0.0.1:5173";
const API = process.env.MAYABU_API_URL || "http://127.0.0.1:8000";
const OUT = path.resolve("visual-qa-ux-v1");

const viewports = [
  { name: "360", width: 360, height: 800 },
  { name: "390", width: 390, height: 844 },
  { name: "430", width: 430, height: 932 },
  { name: "768", width: 768, height: 1024 },
  { name: "820", width: 820, height: 1180 },
  { name: "1024", width: 1024, height: 768 },
  { name: "1280", width: 1280, height: 800 },
  { name: "1366", width: 1366, height: 768 },
  { name: "1440", width: 1440, height: 900 },
  { name: "1536", width: 1536, height: 864 },
  { name: "1920", width: 1920, height: 1080 },
];

/** Core pages at all widths; heavy pages only at key widths. */
const priorityWidths = new Set(["390", "768", "1366", "1920"]);

async function resolveProductPath() {
  const candidates = [
    `${API}/api/search?q=asus&limit=1`,
    `${API}/api/v1/search?q=asus&limit=1`,
  ];
  for (const url of candidates) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const body = await res.json();
      const item = body?.results?.[0] ?? body?.items?.[0] ?? body?.products?.[0];
      if (!item?.id) continue;
      const slug =
        typeof item.slug === "string" && item.slug
          ? item.slug
          : String(item.title || "product")
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, "-")
              .replace(/^-|-$/g, "")
              .slice(0, 80);
      return `/products/${encodeURIComponent(item.id)}/${slug}`;
    } catch {
      /* try next */
    }
  }
  return null;
}

const productPath = await resolveProductPath();

const coreRoutes = [
  { id: "home", path: "/" },
  { id: "how-it-works", path: "/how-it-works" },
  { id: "about", path: "/about" },
  { id: "contact", path: "/contact" },
  { id: "search", path: "/search?q=asus" },
  { id: "laptops", path: "/laptops" },
  { id: "sign-in", path: "/sign-in" },
  { id: "signup", path: "/signup" },
  { id: "forgot-password", path: "/forgot-password" },
  { id: "wishlist", path: "/wishlist" },
  { id: "compare", path: "/compare" },
];

if (productPath) {
  coreRoutes.push({ id: "pdp", path: productPath });
}

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
let count = 0;
const issues = [];

async function settlePage(page) {
  await page.waitForTimeout(500);
  // Trigger scroll reveals / lazy content without leaving permanent opacity holes.
  await page.evaluate(async () => {
    const delay = (ms) => new Promise((r) => setTimeout(r, ms));
    const height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
    const step = Math.max(320, Math.floor(window.innerHeight * 0.7));
    for (let y = 0; y < height; y += step) {
      window.scrollTo(0, y);
      await delay(60);
    }
    window.scrollTo(0, 0);
    await delay(200);
  });
}

for (const vp of viewports) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
  const routesForVp = priorityWidths.has(vp.name)
    ? coreRoutes
    : coreRoutes.filter((r) =>
        ["home", "how-it-works", "about", "search", "pdp", "compare"].includes(r.id),
      );

  for (const route of routesForVp) {
    const url = `${BASE}${route.path}`;
    try {
      const response = await page.goto(url, { waitUntil: "networkidle", timeout: 45_000 });
      const status = response?.status() ?? 0;
      await settlePage(page);
      const overflow = await page.evaluate(() => {
        const doc = document.documentElement;
        return {
          scrollWidth: doc.scrollWidth,
          clientWidth: doc.clientWidth,
          overflowX: doc.scrollWidth > doc.clientWidth + 2,
        };
      });
      if (overflow.overflowX) {
        issues.push(
          `${route.id}@${vp.name}: horizontal overflow ${overflow.scrollWidth}>${overflow.clientWidth}`,
        );
      }
      if (status >= 500) {
        issues.push(`${route.id}@${vp.name}: HTTP ${status}`);
      }
      const file = path.join(OUT, `${route.id}-${vp.name}.png`);
      await page.screenshot({ path: file, fullPage: true });
      count += 1;
      console.log(`OK ${file} status=${status} overflowX=${overflow.overflowX}`);
    } catch (error) {
      issues.push(`${route.id}@${vp.name}: ${error instanceof Error ? error.message : String(error)}`);
      console.error(`FAIL ${route.id}@${vp.name}`, error);
    }
  }
  await page.close();
}

await browser.close();
console.log(`screenshots=${count} productPath=${productPath ?? "none"} issues=${issues.length}`);
for (const issue of issues) console.log(`ISSUE ${issue}`);
process.exit(issues.length ? 1 : 0);

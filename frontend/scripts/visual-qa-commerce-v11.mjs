/**
 * Commerce UX V1.1 visual QA.
 * Requires FE at http://127.0.0.1:5173 and API at http://127.0.0.1:8000
 */
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const BASE = process.env.MAYABU_FE_URL || "http://127.0.0.1:5173";
const API = process.env.MAYABU_API_URL || "http://127.0.0.1:8000";
const OUT = path.resolve("visual-qa-commerce-v11");

const viewports = [
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "820", width: 820, height: 1180 },
  { name: "1024", width: 1024, height: 768 },
  { name: "1366", width: 1366, height: 768 },
  { name: "1920", width: 1920, height: 1080 },
];

async function resolveIds() {
  try {
    const res = await fetch(`${API}/api/search?q=asus&limit=4`);
    if (!res.ok) return { productPath: null, compare2: "/compare", compare4: "/compare" };
    const body = await res.json();
    const items = body?.results ?? [];
    const first = items[0];
    if (!first?.id) return { productPath: null, compare2: "/compare", compare4: "/compare" };
    const slug = String(first.title || "product")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 80);
    const ids = items.map((item) => item.id).filter(Boolean);
    return {
      productPath: `/products/${encodeURIComponent(first.id)}/${slug}`,
      compare2: `/compare?ids=${ids.slice(0, 2).join(",")}`,
      compare4: `/compare?ids=${ids.slice(0, 4).join(",")}`,
    };
  } catch {
    return { productPath: null, compare2: "/compare", compare4: "/compare" };
  }
}

const resolved = await resolveIds();

const routes = [
  { id: "search", path: "/search?q=asus" },
  { id: "search-empty", path: "/search?q=zzzznotaproduct" },
  { id: "laptops", path: "/laptops" },
  { id: "compare-empty", path: "/compare" },
  { id: "compare-2", path: resolved.compare2 },
  { id: "compare-4", path: resolved.compare4 },
  { id: "wishlist", path: "/wishlist" },
  { id: "account", path: "/account" },
];
if (resolved.productPath) routes.push({ id: "pdp", path: resolved.productPath });

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
let count = 0;
const issues = [];

for (const vp of viewports) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
  for (const route of routes) {
    try {
      const response = await page.goto(`${BASE}${route.path}`, {
        waitUntil: "networkidle",
        timeout: 45_000,
      });
      await page.waitForTimeout(350);
      if (route.id === "pdp") {
        const evidence = page.getByRole("button", { name: /Price evidence/i });
        if (await evidence.count()) {
          await evidence.first().click().catch(() => {});
          await page.waitForTimeout(150);
          await page.screenshot({
            path: path.join(OUT, `pdp-evidence-${vp.name}.png`),
            fullPage: true,
          });
          count += 1;
        }
      }
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
      );
      const rawToken = await page.evaluate(() => {
        const text = document.body?.innerText || "";
        return /amd_ryzen:|front_load|body_only|intel_celeron:/.test(text);
      });
      if (overflow) issues.push(`${route.id}@${vp.name}: overflow`);
      if (rawToken) issues.push(`${route.id}@${vp.name}: raw internal token visible`);
      await page.screenshot({ path: path.join(OUT, `${route.id}-${vp.name}.png`), fullPage: true });
      count += 1;
      console.log(
        `OK ${route.id}-${vp.name} status=${response?.status()} overflow=${overflow} rawToken=${rawToken}`,
      );
    } catch (error) {
      issues.push(`${route.id}@${vp.name}: ${error instanceof Error ? error.message : String(error)}`);
      console.error("FAIL", route.id, vp.name, error);
    }
  }
  await page.close();
}

await browser.close();
console.log(`screenshots=${count} issues=${issues.length} pdp=${resolved.productPath ?? "none"}`);
for (const issue of issues) console.log(`ISSUE ${issue}`);
process.exit(issues.length ? 1 : 0);

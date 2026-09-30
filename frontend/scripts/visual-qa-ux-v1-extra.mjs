/**
 * Extra UX V1 captures: PDP, account/auth/legal.
 */
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const BASE = process.env.MAYABU_FE_URL || "http://127.0.0.1:5173";
const OUT = path.resolve("visual-qa-ux-v1");
const PRODUCT =
  process.env.MAYABU_PDP_PATH ||
  "/products/1211b369-3b40-474c-b4f2-6847f1e6dfc8/asus-tuf-gaming-a15-fa506ncq-hn007ws-gaming-laptop";

const viewports = [
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "1366", width: 1366, height: 768 },
  { name: "1920", width: 1920, height: 1080 },
];

const routes = [
  { id: "pdp", path: PRODUCT },
  { id: "compare-2", path: `/compare?ids=${PRODUCT.split("/")[2]}` },
  { id: "account", path: "/account" },
  { id: "check-email", path: "/check-email" },
  { id: "reset-password", path: "/reset-password" },
  { id: "privacy", path: "/privacy" },
  { id: "terms", path: "/terms" },
];

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
      await page.waitForTimeout(400);
      await page.evaluate(async () => {
        const delay = (ms) => new Promise((r) => setTimeout(r, ms));
        const height = Math.max(document.body.scrollHeight, 1200);
        for (let y = 0; y < height; y += 420) {
          window.scrollTo(0, y);
          await delay(40);
        }
        window.scrollTo(0, 0);
      });
      // Expand Price Evidence on PDP when present
      if (route.id === "pdp") {
        const btn = page.getByRole("button", { name: /Price evidence/i });
        if (await btn.count()) {
          await btn.first().click().catch(() => {});
          await page.waitForTimeout(200);
          await page.screenshot({
            path: path.join(OUT, `pdp-evidence-open-${vp.name}.png`),
            fullPage: true,
          });
          count += 1;
        }
      }
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
      );
      if (overflow) issues.push(`${route.id}@${vp.name}: overflow`);
      await page.screenshot({
        path: path.join(OUT, `${route.id}-${vp.name}.png`),
        fullPage: true,
      });
      count += 1;
      console.log(`OK ${route.id}-${vp.name} status=${response?.status()} overflow=${overflow}`);
    } catch (error) {
      issues.push(`${route.id}@${vp.name}: ${error instanceof Error ? error.message : String(error)}`);
      console.error("FAIL", route.id, vp.name, error);
    }
  }
  await page.close();
}

await browser.close();
console.log(`extra screenshots=${count} issues=${issues.length}`);
for (const issue of issues) console.log(`ISSUE ${issue}`);
process.exit(issues.length ? 1 : 0);

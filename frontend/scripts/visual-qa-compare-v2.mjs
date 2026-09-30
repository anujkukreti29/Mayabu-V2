import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const outDir = path.resolve("artifacts/compare-v2");
fs.mkdirSync(outDir, { recursive: true });

const cases = [
  { name: "laptop-2", path: "/compare?ids=p1,p2" },
  { name: "phone-2", path: "/compare?ids=phone-1,phone-2" },
  { name: "tv-2", path: "/compare?ids=tv-1,tv-2" },
  { name: "camera-2", path: "/compare?ids=cam-1,cam-2" },
  { name: "laptop-4", path: "/compare?ids=p1,p2,p3,p4" },
];

const viewports = [
  { name: "390x844", width: 390, height: 844 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

const browser = await chromium.launch();
const page = await browser.newPage();
const report = [];

for (const vp of viewports) {
  await page.setViewportSize({ width: vp.width, height: vp.height });
  for (const testCase of cases.filter((item) => !(item.name === "laptop-4" && vp.width < 1000))) {
    await page.goto(`http://127.0.0.1:5173${testCase.path}`, { waitUntil: "networkidle" });
    const file = path.join(outDir, `${vp.name}-${testCase.name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    const metrics = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      h1: document.querySelector("h1")?.textContent?.trim() ?? null,
      hasTable: Boolean(document.querySelector("table")),
    }));
    report.push({ viewport: vp.name, case: testCase.name, ...metrics, file });
  }
}

// Dedicated 4-product same-category shot using repeated laptop+variant via search tray is hard in mock;
// capture camera+body as 2-product mobile already covered.
console.log(JSON.stringify(report, null, 2));
const failures = report.filter((row) => row.overflow || !row.h1);
if (failures.length) {
  console.error("Compare visual QA failures", failures.length);
  process.exitCode = 1;
}
await browser.close();

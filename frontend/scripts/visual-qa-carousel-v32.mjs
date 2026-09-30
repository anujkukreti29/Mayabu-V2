import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const outDir = path.resolve("artifacts/homepage-v32-carousel");
fs.mkdirSync(outDir, { recursive: true });

const viewports = [
  { name: "390x844", width: 390, height: 844 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

const slideTargets = [
  { key: "slide1-mosaic", nextClicks: 0 },
  { key: "slide2-grid", nextClicks: 1 },
  { key: "slide3-grid", nextClicks: 2 },
  { key: "slide5-featured", nextClicks: 4 },
];

const browser = await chromium.launch();
const page = await browser.newPage();
const summary = [];

for (const vp of viewports) {
  await page.setViewportSize({ width: vp.width, height: vp.height });
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });
  const carousel = page.getByRole("region", { name: "Mayabu homepage highlights" });
  await carousel.waitFor({ state: "visible" });

  for (const target of slideTargets) {
    await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });
    for (let i = 0; i < target.nextClicks; i += 1) {
      await page.getByRole("button", { name: "Next slide" }).click();
      await page.waitForTimeout(450);
    }
    const file = path.join(outDir, `${vp.name}-${target.key}.png`);
    await carousel.screenshot({ path: file });
    const heading = await page
      .locator('[aria-roledescription="slide"]:not([aria-hidden="true"]) h3')
      .first()
      .textContent();
    summary.push({ viewport: vp.name, slide: target.key, heading: heading?.trim() ?? null, file });
  }

  const full = path.join(outDir, `${vp.name}-fullpage.png`);
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });
  await page.screenshot({ path: full, fullPage: true });
}

console.log(JSON.stringify(summary, null, 2));
await browser.close();

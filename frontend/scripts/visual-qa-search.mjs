import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const baseURL = process.env.VISUAL_QA_BASE_URL || "http://127.0.0.1:5173";
const outDir = path.resolve("test-results/visual-qa-search");
fs.mkdirSync(outDir, { recursive: true });

const viewports = [
  { name: "390x844", width: 390, height: 844 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "1024x768", width: 1024, height: 768 },
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

const queries = [
  { name: "laptop", path: "/search?q=ASUS+Vivobook" },
  { name: "smartphone", path: "/search?q=Galaxy+S24" },
  { name: "tv", path: "/search?q=55+inch+OLED+TV" },
  { name: "refrigerator", path: "/search?q=260L+refrigerator" },
  { name: "washer", path: "/search?q=8kg+front+load+washing+machine" },
  { name: "tws", path: "/search?q=ANC+earbuds" },
  { name: "headphones", path: "/search?q=Sony+WH-1000XM5" },
  { name: "mixed-samsung", path: "/search?q=Samsung" },
];

const browser = await chromium.launch();
const page = await browser.newPage();
const report = [];

for (const vp of viewports) {
  await page.setViewportSize({ width: vp.width, height: vp.height });
  for (const query of queries) {
    await page.goto(`${baseURL}${query.path}`, { waitUntil: "networkidle" });
    const shot = `${query.name}__${vp.name}.png`;
    await page.screenshot({
      path: path.join(outDir, shot),
      fullPage: true,
    });
    const metrics = await page.evaluate(() => {
      const main = document.querySelector("main");
      const cards = [...document.querySelectorAll("main a[href*='/products/']")].filter((el) =>
        el.querySelector("img, [aria-label*='image' i], p"),
      );
      const productCards = [...document.querySelectorAll("main article, main li")].length;
      const h1 = document.querySelector("h1");
      const aside = document.querySelector("aside");
      const filtersBtn = [...document.querySelectorAll("button")].find((b) =>
        /filters/i.test(b.textContent || ""),
      );
      const images = [...document.querySelectorAll("main img")].map((img) => {
        const rect = img.getBoundingClientRect();
        return {
          w: Math.round(rect.width),
          h: Math.round(rect.height),
          objectFit: getComputedStyle(img).objectFit,
        };
      });
      const overflow = document.documentElement.scrollWidth > window.innerWidth + 1;
      return {
        h1: h1?.textContent?.trim() ?? null,
        h1Font: h1 ? getComputedStyle(h1).fontSize : null,
        asideVisible: aside
          ? getComputedStyle(aside).display !== "none" && aside.getBoundingClientRect().width > 0
          : false,
        filtersButtonVisible: filtersBtn
          ? getComputedStyle(filtersBtn).display !== "none" &&
            filtersBtn.getBoundingClientRect().width > 0
          : false,
        cardishCount: productCards,
        productLinkCount: cards.length,
        images,
        overflow,
        mainWidth: main ? Math.round(main.getBoundingClientRect().width) : null,
      };
    });
    report.push({ viewport: vp.name, query: query.name, screenshot: shot, ...metrics });
  }
}

fs.writeFileSync(path.join(outDir, "report.json"), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();

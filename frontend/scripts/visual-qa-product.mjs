import { chromium } from "@playwright/test";

const viewports = [
  { name: "390x844", width: 390, height: 844 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "1024x768", width: 1024, height: 768 },
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

const pages = [
  { name: "laptop", path: "/products/p1/asus-vivobook-15-x1504va-16gb-512gb" },
  { name: "smartphone", path: "/products/phone-1/samsung-galaxy-s24-8gb-256gb" },
  { name: "tv", path: "/products/tv-1/samsung-55-inch-4k-qled-smart-tv" },
  { name: "fridge", path: "/products/fridge-1/lg-260l-frost-free-refrigerator" },
  { name: "washer", path: "/products/washer-1/lg-8-kg-front-load-washing-machine" },
  { name: "camera", path: "/products/cam-1/sony-alpha-a7-iv-body-only" },
  { name: "tws", path: "/products/tws-1/sony-wf-1000xm5-anc-earbuds" },
  { name: "headphones", path: "/products/hp-1/sony-wh-1000xm5-wireless-headphones" },
];

const browser = await chromium.launch();
const page = await browser.newPage();
const report = [];

for (const target of pages) {
  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    const response = await page.goto(`http://127.0.0.1:5173${target.path}`, {
      waitUntil: "networkidle",
    });
    const metrics = await page.evaluate(() => {
      const h1 = document.querySelector("h1");
      const imageFrame = document.querySelector(
        "#main-content img, #main-content [class*='aspect-']",
      );
      const offers = document.querySelector('[aria-label="Retailer offers"]');
      const history = [...document.querySelectorAll("h2")].find((el) =>
        /Price history/i.test(el.textContent || ""),
      );
      const rect = imageFrame?.getBoundingClientRect();
      return {
        statusOk: true,
        h1: h1?.textContent?.trim().slice(0, 80) ?? null,
        hasOffers: Boolean(offers),
        hasHistory: Boolean(history),
        imageW: rect ? Math.round(rect.width) : null,
        imageH: rect ? Math.round(rect.height) : null,
        overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      };
    });
    report.push({
      page: target.name,
      viewport: vp.name,
      http: response?.status() ?? null,
      ...metrics,
      statusOk: (response?.status() ?? 500) < 400,
    });
  }
}

console.log(JSON.stringify(report, null, 2));
const failures = report.filter((row) => !row.statusOk || row.overflow);
if (failures.length) {
  console.error("Visual QA failures:", failures.length);
  process.exitCode = 1;
}
await browser.close();

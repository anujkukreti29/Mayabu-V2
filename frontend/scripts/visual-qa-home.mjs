import { chromium } from "@playwright/test";

const viewports = [
  { name: "390x844", width: 390, height: 844 },
  { name: "768x1024", width: 768, height: 1024 },
  { name: "1024x768", width: 1024, height: 768 },
  { name: "1366x768", width: 1366, height: 768 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1920x1080", width: 1920, height: 1080 },
];

const browser = await chromium.launch();
const page = await browser.newPage();
const report = [];

for (const vp of viewports) {
  await page.setViewportSize({ width: vp.width, height: vp.height });
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });
  const metrics = await page.evaluate(() => {
    const logo = document.querySelector('a[aria-label="Mayabu home"] img');
    const header = document.querySelector("header");
    const h1 = document.querySelector("h1");
    const carousel = document.querySelector('[aria-roledescription="carousel"]');
    const prev = document.querySelector('[aria-label="Previous slide"]');
    const activeTitle = document.querySelector(
      '[aria-roledescription="slide"]:not([aria-hidden="true"]) h3',
    );
    const wishlist = document.querySelector('button[aria-label="Wishlist"]');
    const logoRect = logo?.getBoundingClientRect();
    const headerRect = header?.getBoundingClientRect();
    const prevRect = prev?.getBoundingClientRect();
    const titleRect = activeTitle?.getBoundingClientRect();
    const overlap =
      prevRect && titleRect
        ? !(
            prevRect.right < titleRect.left ||
            prevRect.left > titleRect.right ||
            prevRect.bottom < titleRect.top ||
            prevRect.top > titleRect.bottom
          )
        : false;
    return {
      logoH: logoRect ? Math.round(logoRect.height) : null,
      headerH: headerRect ? Math.round(headerRect.height) : null,
      h1: h1?.textContent?.trim().slice(0, 80) ?? null,
      hasCarousel: Boolean(carousel),
      arrowOverlapsTitle: overlap,
      hasWishlist: Boolean(wishlist),
      hasRecent: Boolean(
        [...document.querySelectorAll("h2")].find((el) =>
          /Freshly Checked|Recently Verified|Recently Checked/i.test(el.textContent || ""),
        ),
      ),
      hasStores: Boolean(
        [...document.querySelectorAll("h2")].find((el) =>
          /Supported Stores/i.test(el.textContent || ""),
        ),
      ),
      hasWhy: Boolean(
        [...document.querySelectorAll("h2")].find((el) => /Why Mayabu/i.test(el.textContent || "")),
      ),
      hasCategoryGrid: Boolean(
        [...document.querySelectorAll("h2")].find((el) =>
          /Quick categories|Shop by Category/i.test(el.textContent || ""),
        ),
      ),
      overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    };
  });
  report.push({ viewport: vp.name, ...metrics });
}

console.log(JSON.stringify(report, null, 2));
const failures = report.filter(
  (row) =>
    row.overflow ||
    row.arrowOverlapsTitle ||
    !row.hasCarousel ||
    row.hasStores ||
    row.hasWhy ||
    row.hasCategoryGrid,
);
if (failures.length) {
  console.error("Visual QA failures:", failures.length);
  process.exitCode = 1;
}
await browser.close();

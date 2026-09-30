import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "visual-qa-v2");
mkdirSync(root, { recursive: true });

const viewports = [
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "1366", width: 1366, height: 768 },
  { name: "1920", width: 1920, height: 1080 },
];

const pages = [
  { name: "home", path: "/" },
  { name: "laptops", path: "/laptops" },
  { name: "search", path: "/search?q=asus" },
  { name: "signin", path: "/sign-in" },
  { name: "signup", path: "/signup" },
];

const browser = await chromium.launch();
const report = [];

for (const vp of viewports) {
  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
  });
  const page = await context.newPage();

  for (const route of pages) {
    await page.goto(`http://127.0.0.1:5173${route.path}`, {
      waitUntil: "networkidle",
      timeout: 60_000,
    });
    const file = join(root, `${route.name}-${vp.name}.png`);
    await page.screenshot({ path: file, fullPage: route.name === "home" });
    report.push({ route: route.name, viewport: vp.name, file });
  }

  // Homepage carousel progress mid-frame + title boxes
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle", timeout: 60_000 });
  await page.waitForTimeout(1400);
  await page.screenshot({
    path: join(root, `home-carousel-mid-${vp.name}.png`),
    fullPage: false,
  });
  const titleAudit = await page.evaluate(() => {
    const active = document.querySelector(
      '[aria-roledescription="slide"]:not([aria-hidden="true"])',
    );
    const titles = [
      ...active?.querySelectorAll(
        "[data-testid='carousel-mosaic-title'], [data-testid='carousel-product-title']",
      ) ?? [],
    ];
    return titles.map((el) => {
      const box = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return {
        text: (el.textContent || "").trim().slice(0, 60),
        w: Math.round(box.width),
        h: Math.round(box.height),
        display: style.display,
        visibility: style.visibility,
        ok: box.height > 8 && box.width > 20 && style.display !== "none",
      };
    });
  });
  report.push({ route: "home-titles", viewport: vp.name, titleAudit });

  // Non-home navbar search containment
  await page.goto("http://127.0.0.1:5173/laptops", {
    waitUntil: "networkidle",
    timeout: 60_000,
  });
  await page.screenshot({ path: join(root, `nav-laptops-${vp.name}.png`), fullPage: false });
  if (vp.width >= 1024) {
    const navAudit = await page.evaluate(() => {
      const form = document.querySelector("#nav-search")?.closest("form");
      const input = document.querySelector("#nav-search");
      const button = form?.querySelector('button[type="submit"]');
      const formBox = form?.getBoundingClientRect();
      const inputBox = input?.getBoundingClientRect();
      const buttonBox = button?.getBoundingClientRect();
      const inside =
        formBox && inputBox && buttonBox
          ? inputBox.left >= formBox.left - 1 &&
            buttonBox.right <= formBox.right + 1 &&
            inputBox.top >= formBox.top - 1 &&
            buttonBox.bottom <= formBox.bottom + 1
          : false;
      return {
        formW: formBox ? Math.round(formBox.width) : null,
        inside,
        hasDiscover: Boolean(
          [...document.querySelectorAll("a")].find((a) => a.textContent?.trim() === "Discover"),
        ),
        hasLive: Boolean(
          [...document.querySelectorAll("span,a,button")].find(
            (el) => el.textContent?.trim() === "Live",
          ),
        ),
      };
    });
    report.push({ route: "nav-audit", viewport: vp.name, navAudit });
  }

  await context.close();
}

await browser.close();
console.log(JSON.stringify(report, null, 2));
const titleFails = report
  .filter((row) => row.titleAudit)
  .flatMap((row) => row.titleAudit.filter((t) => !t.ok));
const navFails = report.filter((row) => row.navAudit && (!row.navAudit.inside || row.navAudit.hasDiscover || row.navAudit.hasLive));
if (titleFails.length || navFails.length) {
  console.error("VISUAL_QA_FAIL", { titleFails, navFails });
  process.exit(1);
}
console.log(`Wrote ${report.filter((r) => r.file).length} screenshots to ${root}`);

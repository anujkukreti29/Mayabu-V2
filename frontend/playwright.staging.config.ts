import { defineConfig, devices } from "@playwright/test";

/**
 * E2E against a deployed HTTPS staging origin.
 * Refuses localhost. Does not start a dev server.
 *
 *   STAGING_BASE_URL=https://staging.example npx playwright test --config=playwright.staging.config.ts --project=chromium --workers=2 --retries=0
 */
const baseURL = (process.env.STAGING_BASE_URL || "").trim().replace(/\/$/, "");
const configuredChromium = process.env.PLAYWRIGHT_CHROMIUM_PATH;

function assertStagingOrigin(url: string): string {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error("STAGING_BASE_URL must be an absolute https:// URL");
  }
  const host = parsed.hostname.toLowerCase();
  const local = host === "localhost" || host === "127.0.0.1" || host === "::1" || host.endsWith(".local");
  if (parsed.protocol !== "https:" || local) {
    throw new Error("STAGING_BASE_URL must be public HTTPS. Localhost is not staging.");
  }
  return parsed.origin;
}

const origin = assertStagingOrigin(baseURL);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  workers: 2,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report-staging" }]],
  use: {
    baseURL: origin,
    trace: "retain-on-failure",
    launchOptions: configuredChromium ? { executablePath: configuredChromium } : undefined,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
    {
      name: "tablet",
      use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 } },
    },
  ],
});

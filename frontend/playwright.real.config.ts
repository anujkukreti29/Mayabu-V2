import { defineConfig, devices } from "@playwright/test";

const configuredChromium = process.env.PLAYWRIGHT_CHROMIUM_PATH;

/** Real-backend browser suite — requires API on :8000. */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: true,
  retries: 1,
  workers: process.env.CI ? 2 : undefined,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report-real" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    launchOptions: configuredChromium ? { executablePath: configuredChromium } : undefined,
  },
  webServer: {
    command: "node scripts/start-e2e-real.mjs",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
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

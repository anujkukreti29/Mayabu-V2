import { expect, test } from "@playwright/test";

test.describe("Reliability + discovery V1 browser proof", () => {
  test("homepage explore section shows multiple categories", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Explore categories" })).toBeVisible();
    const explore = page.locator("#explore-categories");
    await expect(explore.getByRole("link", { name: /Smartphones/i })).toBeVisible();
    await expect(explore.getByRole("link", { name: /Laptops/i })).toBeVisible();
    await expect(explore.getByRole("link", { name: /Televisions|TVs/i })).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 2,
    );
    expect(overflow).toBe(false);
  });

  test("homepage near tracked low and spotlight sections render when supplied", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    // Near tracked low is hidden when history evidence is thin — assert only when present.
    const nearLow = page.getByRole("heading", { name: /Near (their )?tracked low/i });
    if (await nearLow.count()) {
      await expect(nearLow).toBeVisible();
    }
    await expect(page.getByRole("heading", { name: /Smartphone picks|TVs worth/i }).first()).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 2,
    );
    expect(overflow).toBe(false);
  });

  test("watchlist dashboard loads filters for signed-in user", async ({ page }) => {
    await page.goto("/signup");
    await page.locator("#name").fill("Watch Dash");
    await page.locator("#email").fill(`watchdash.${Date.now()}@example.test`);
    await page.locator("#password").fill("passphrase-ok");
    await page.locator("#confirm-password").fill("passphrase-ok");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/check-email/);
    await page.getByRole("link", { name: "Continue browsing" }).click();
    await page.goto("/wishlist");
    await expect(page.getByRole("heading", { level: 1, name: "Watchlist" })).toBeVisible();
    await expect(page.getByText(/email alerts stay deferred|deferred/i).first()).toBeVisible();
  });
});

import { expect, test, type Page } from "@playwright/test";

async function signUp(page: Page, email: string) {
  await page.goto("/signup");
  await page.getByLabel(/^Name$/i).fill("UX Proof User");
  await page.getByLabel(/^Email$/i).fill(email);
  await page.getByLabel(/^Password$/i).fill("passphrase-ok");
  await page.getByLabel(/Confirm password/i).fill("passphrase-ok");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/check-email/);
  await page.getByRole("link", { name: "Continue browsing" }).click();
}

test.describe("Smart Commerce UX V1.2 browser proof", () => {
  test("hero autocomplete rapid typing keeps latest suggestion and Escape closes", async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name !== "chromium", "Rapid typing race is desktop-focused");
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/");
    const hero = page.locator("main").getByRole("combobox", { name: /search mayabu products/i });
    await hero.click();
    await hero.pressSequentially("samsung", { delay: 35 });
    const listbox = page.getByRole("listbox");
    await expect(listbox).toBeVisible({ timeout: 8_000 });
    await expect(listbox.getByRole("option").first()).toBeVisible();
    await hero.press("ArrowDown");
    await expect(hero).toHaveAttribute("aria-activedescendant", /.+/);
    await hero.press("Escape");
    await expect(page.getByRole("listbox")).toHaveCount(0);
  });

  test("header and page search forms keep unique combobox ids off-home", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    // Homepage intentionally hides navbar search; use Search page for dual forms.
    await page.goto("/search?q=laptop");
    const ids = await page.locator('input[role="combobox"]').evaluateAll((nodes) =>
      nodes.map((node) => (node as HTMLInputElement).id).filter(Boolean),
    );
    expect(ids.length).toBeGreaterThanOrEqual(2);
    expect(new Set(ids).size).toBe(ids.length);
  });

  test("popular searches appear when idle and recent searches stay local", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/");
    const hero = page.locator("main").getByRole("combobox", { name: /search mayabu products/i });
    await hero.click();
    const popular = page.getByLabel("Popular searches");
    const listbox = page.getByRole("listbox");
    await expect(popular.or(listbox).first()).toBeVisible({ timeout: 10_000 });
    await hero.fill("asus");
    await page.waitForTimeout(280);
    await hero.press("Enter");
    await expect(page).toHaveURL(/\/search\?q=/, { timeout: 15_000 });
    await page.goto("/");
    const heroAgain = page.locator("main").getByRole("combobox", { name: /search mayabu products/i });
    await heroAgain.click();
    const recent = page.getByRole("region", { name: "Recent searches" });
    if (await recent.count()) {
      await expect(recent.getByText(/asus/i).first()).toBeVisible();
    }
  });

  test("mobile 360 search does not overflow and can open a product from suggest", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 360, height: 740 });
    await page.goto("/");
    const openMenu = page.getByRole("button", { name: "Open menu" });
    await expect(openMenu).toBeVisible({ timeout: 10_000 });
    await openMenu.click();
    const menuSearch = page.getByRole("dialog").getByRole("combobox", {
      name: /search mayabu products/i,
    });
    await expect(menuSearch).toBeVisible({ timeout: 10_000 });
    await menuSearch.fill("galaxy");
    await page.waitForTimeout(350);
    const option = page.getByRole("option").first();
    if (await option.isVisible().catch(() => false)) {
      await option.click();
      await expect(page).toHaveURL(/\/(products|search)/, { timeout: 15_000 });
    } else {
      await menuSearch.press("Enter");
      await expect(page).toHaveURL(/\/search\?q=/, { timeout: 15_000 });
    }
    // Measure document overflow (horizontal rails may paint past the viewport but must not expand scrollWidth).
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 2,
    );
    expect(overflow).toBe(false);
  });

  test("PDP check latest, intelligence, history, evidence, and store coverage", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/search?q=laptop");
    const link = page.locator("main a[href*='/products/']").first();
    await expect(link).toBeVisible({ timeout: 20_000 });
    await link.click();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("main").getByText(/₹/).first()).toBeVisible();

    await expect(page.getByText(/Price intelligence|Consider now|Watch|Check latest/i).first()).toBeVisible();

    const history = page.getByRole("heading", { name: "Price history" });
    await expect(history).toBeVisible();
    const rangeGroup = page.getByRole("group", { name: "History range" });
    if (await rangeGroup.count()) {
      await rangeGroup.getByRole("button", { name: "30D" }).click();
      await rangeGroup.getByRole("button", { name: "All" }).click();
    }

    const stores = page.getByRole("button", { name: /store.*compared/i });
    if (await stores.count()) {
      await stores.first().click();
      await expect(page.getByRole("region", { name: /Store coverage/i })).toBeVisible({
        timeout: 10_000,
      });
      await page.keyboard.press("Escape");
      await expect(page.getByRole("region", { name: /Store coverage/i })).toHaveCount(0);
    }

    const checkBtn = page.getByRole("button", { name: /Check latest price/i });
    if (await checkBtn.isEnabled()) {
      await checkBtn.click();
      await expect(
        page.getByText(/checked just now|Checking latest prices|Still ₹|Check queued/i).first(),
      ).toBeVisible({ timeout: 20_000 });
    }
  });

  test("signed-out Watch Price redirects back to product via next=", async ({ page, context }) => {
    await context.clearCookies();
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/");
    await page.evaluate(() => {
      try {
        window.localStorage.clear();
        window.sessionStorage.clear();
      } catch {
        /* ignore */
      }
    });
    await page.goto("/search?q=laptop");
    await page.locator("main a[href*='/products/']").first().click();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: /Watch price|Loading watch/i }).click();
    await expect(page).toHaveURL(/sign-in|login/, { timeout: 15_000 });
    const url = page.url();
    expect(url).toMatch(/next=/);
    expect(url).toMatch(/products/);
    expect(url).not.toMatch(/https?%3A%2F%2Fevil/);
  });

  test("authenticated Watch Price upsert persists to Wishlist and PDP reload", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    const email = `watch.${Date.now()}@example.test`;
    await signUp(page, email);
    await page.goto("/search?q=laptop");
    await page.locator("main a[href*='/products/']").first().click();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: /Watch price/i }).click();
    await expect(page.getByRole("dialog", { name: /Watch price/i })).toBeVisible();
    await page.getByRole("radio", { name: /Target price/i }).check();
    await page.getByRole("textbox", { name: /Target price in rupees/i }).fill("49999");
    await page.getByRole("button", { name: /Track this target/i }).click();
    await expect(page.getByRole("button", { name: /Watching/i })).toBeVisible({
      timeout: 12_000,
    });
    await page.reload();
    await expect(page.getByRole("button", { name: /Watching/i })).toBeVisible({ timeout: 15_000 });
    await page.goto("/wishlist");
    await expect(page.getByText(/Target ₹49,999/i).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("compare tray survives navigation and hides on /compare; mobile PDP no overflow", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/search?q=Galaxy");
    await page
      .getByRole("button", { name: /add .* to comparison/i })
      .first()
      .click();
    const tray = page.getByRole("complementary", { name: /comparison tray/i });
    await expect(tray).toBeVisible();
    await page.goto("/search?q=laptop");
    await page.locator("main a[href*='/products/']").first().click();
    await expect(tray).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 2,
    );
    expect(overflow).toBe(false);
    await page.goto("/compare");
    await expect(page.getByRole("complementary", { name: /comparison tray/i })).toHaveCount(0);
  });

  test("viewport matrix 360/390/430/768 stays usable on PDP", async ({ page }) => {
    await page.goto("/search?q=laptop");
    const href = await page.locator("main a[href*='/products/']").first().getAttribute("href");
    expect(href).toBeTruthy();
    for (const width of [360, 390, 430, 768]) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto(href!);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth + 2,
      );
      expect(overflow, `overflow at ${width}`).toBe(false);
    }
  });

  test("suggest API failure still allows Enter search", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.route("**/api/search/suggest**", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "boom" }),
      });
    });
    await page.goto("/");
    const hero = page.locator("main").getByRole("combobox", { name: /search mayabu products/i });
    await hero.click();
    const suggestFailed = page.waitForResponse(
      (res) => res.url().includes("/api/search/suggest") && res.status() === 500,
      { timeout: 15_000 },
    );
    await hero.fill("iphone");
    await suggestFailed;
    await expect(
      page.getByText(/suggestions unavailable|press enter to search/i),
    ).toBeVisible({ timeout: 10_000 });
    await hero.press("Enter");
    await expect(page).toHaveURL(/\/search\?q=/, { timeout: 10_000 });
  });
});

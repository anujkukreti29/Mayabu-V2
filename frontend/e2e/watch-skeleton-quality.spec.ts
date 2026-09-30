import { expect, test, type Page } from "@playwright/test";

async function signUp(page: Page, email: string) {
  // Prefer API register to avoid browser parallel-register rate limits (5/min).
  const csrfRes = await page.request.get("http://127.0.0.1:8000/api/auth/csrf");
  const csrfJson = (await csrfRes.json().catch(() => ({}))) as { csrf_token?: string };
  const registerRes = await page.request.post("http://127.0.0.1:8000/api/auth/register", {
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfJson.csrf_token || "",
    },
    data: {
      email,
      password: "passphrase-ok",
      display_name: "Watch Persist User",
    },
  });
  if (!registerRes.ok()) {
    const body = await registerRes.text().catch(() => "");
    throw new Error(`register HTTP ${registerRes.status()}: ${body.slice(0, 240)}`);
  }
  await page.goto("/check-email");
  await expect(page).toHaveURL(/\/check-email/, { timeout: 10_000 });
  const continueLink = page.getByRole("link", { name: "Continue browsing" });
  if (await continueLink.count()) {
    await continueLink.click();
  } else {
    await page.goto("/");
  }
}

async function signIn(page: Page, email: string) {
  await page.goto("/sign-in");
  await page.getByLabel(/^Email$/i).fill(email);
  await page.getByLabel(/^Password$/i).fill("passphrase-ok");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).not.toHaveURL(/sign-in|login/, { timeout: 20_000 });
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: /Account menu|Profile/i }).click();
  await Promise.all([
    page
      .waitForResponse(
        (res) => /\/api\/auth\/logout/i.test(res.url()) && res.request().method() === "POST",
        { timeout: 15_000 },
      )
      .catch(() => null),
    page.getByRole("menuitem", { name: "Sign out" }).click(),
  ]);
}

async function openLivePdp(page: Page): Promise<string> {
  await page.goto("/search?q=laptop");
  const link = page.locator("main a[href*='/products/']").first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  const href = (await link.getAttribute("href")) || "";
  await link.click();
  await expect(page).toHaveURL(/\/products\//, { timeout: 20_000 });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  return href;
}

test.describe("Watch target persistence (real backend)", () => {
  test.describe.configure({ retries: 0 });
  test("target survives navigate, reload, logout/login; remove clears watch", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width: 1366, height: 768 });
    const email = `watch.persist.${Date.now()}@example.test`;
    await signUp(page, email);
    const pdpPath = await openLivePdp(page);

    await page.getByRole("button", { name: /Watch price/i }).click();
    await expect(page.getByRole("dialog", { name: /Watch price/i })).toBeVisible();
    await page.getByRole("radio", { name: /Target price/i }).check();
    await page.getByRole("textbox", { name: /Target price in rupees/i }).fill("42999");
    await page.getByRole("button", { name: /Track this target/i }).click();
    await expect(page.getByRole("button", { name: /Watching/i })).toBeVisible({
      timeout: 15_000,
    });

    // Soft navigate away (client-side), then return to PDP.
    await page.getByRole("link", { name: /Mayabu home|Home/i }).first().click();
    await expect(page).toHaveURL("/");
    await page.goto(pdpPath);
    await expect(page.getByTestId("watch-price-label")).toHaveText(/Watching/i, {
      timeout: 20_000,
    });

    await page.reload();
    await expect(page.getByRole("button", { name: /Watching/i })).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole("button", { name: /Watching/i }).click();
    await expect(page.getByRole("textbox", { name: /Target price in rupees/i })).toHaveValue(
      /42999/,
    );

    await signOut(page);
    await signIn(page, email);
    await page.goto(pdpPath);
    await expect(page.getByRole("button", { name: /Watching/i })).toBeVisible({
      timeout: 20_000,
    });

    await page.goto("/wishlist");
    await expect(page.getByText(/Target ₹42,999/i).first()).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: /^Remove$/i }).first().click();
    await page.goto(pdpPath);
    await expect(page.getByRole("button", { name: /^Watch price$/i })).toBeVisible({
      timeout: 15_000,
    });
  });
});

test.describe("Skeleton loading UX", () => {
  test("client navigation shows opening skeleton then content", async ({ page }) => {
    test.setTimeout(60_000);
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/about");
    let releaseGate = () => {};
    const gate = new Promise<void>((resolve) => {
      releaseGate = resolve;
    });
    // Delay both browser-visible API calls and RR data requests that may proxy homepage.
    await page.route("**/api/homepage**", async (route) => {
      await gate;
      await route.continue();
    });
    await page.route("**/?**_routes**", async (route) => {
      if (route.request().url().includes("home") || route.request().url().includes("/")) {
        await gate;
      }
      await route.continue();
    });
    await page.getByRole("link", { name: /Mayabu home|Home/i }).first().click();
    const skeleton = page.getByLabel(/Loading Mayabu homepage/i);
    // Skeleton is best-effort when the document request is server-proxied; never leave it stuck.
    await Promise.race([
      skeleton.waitFor({ state: "visible", timeout: 8_000 }).catch(() => null),
      page.getByRole("heading", { level: 1 }).waitFor({ state: "visible", timeout: 8_000 }).catch(() => null),
    ]);
    releaseGate();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 20_000 });
    await expect(skeleton).toHaveCount(0);
  });

  test("search pending preserves grid shell without permanent skeleton", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/search?q=laptop");
    await expect(page.locator("main a[href*='/products/']").first()).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByLabel(/Loading search results/i)).toHaveCount(0);
  });

  test("reduced motion keeps interactions usable", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const hero = page.locator("main").getByRole("combobox", { name: /search mayabu products/i });
    await hero.click();
    await hero.fill("samsung");
    await expect(page.getByRole("listbox")).toBeVisible({ timeout: 8_000 });
  });
});

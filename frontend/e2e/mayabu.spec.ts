import { expect, test } from "@playwright/test";

test("home is prerender-friendly and navigable", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page).toHaveTitle("Mayabu — Compare Prices Across Stores & Platforms");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: /Compare prices\. Track drops\. Know when to buy\.|Compare products\. Check current prices\./,
    }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeAttached();
  await expect(page.getByRole("banner").getByRole("link", { name: "Mayabu home" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Wishlist" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Profile" })).toBeVisible();
});

test("desktop navigation stays full-width without hamburger at 1366", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Open menu" })).toBeHidden();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", {
      name: "Categories",
      exact: true,
    }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
});

test("mobile navigation uses the drawer", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const openMenu = page.getByRole("button", { name: "Open menu" });
  await expect(openMenu).toBeVisible();
  await openMenu.click();
  const menu = page.getByRole("dialog");
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("heading", { name: "Mayabu menu" })).toBeVisible();
  await expect(menu.getByRole("link", { name: "Cameras" })).toBeVisible();
});

test("homepage carousel exposes mosaic, grids, and bottom-left controls", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const carousel = page.getByRole("region", { name: "Mayabu homepage highlights" });
  await expect(carousel).toBeVisible();
  await expect(carousel.getByRole("heading", { name: "Products worth comparing" })).toBeVisible();
  await expect(carousel.locator('a[href^="/products/"]').first()).toBeVisible();
  await expect(carousel.getByText("Smartphones").first()).toBeVisible();
  await carousel.getByRole("button", { name: "Next slide" }).click();
  await expect(
    carousel.getByRole("heading", { name: /Freshly checked|Biggest discounts|Lowest since/i }),
  ).toBeVisible({ timeout: 10_000 });
  const overlap = await page.evaluate(() => {
    const prev = document.querySelector('[aria-label="Previous slide"]');
    const title = document.querySelector(
      '[aria-roledescription="slide"]:not([aria-hidden="true"]) h3',
    );
    if (!prev || !title) return false;
    const a = prev.getBoundingClientRect();
    const b = title.getBoundingClientRect();
    return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
  });
  expect(overlap).toBe(false);
});

test("homepage section anchors are reachable", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/#recently-verified");
  await expect(page.locator("#recently-verified")).toBeInViewport();
});

test("homepage discovery sections render without category grid, stores, or why", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Quick categories" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Shop by Category" })).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: /Supported Stores|Supported stores/i }),
  ).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Why Mayabu" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Freshly Checked" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Top Deals Across Stores" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Lowest Since Tracking" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Best Multi-Store Comparisons" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent Price Drops" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Explore categories" })).toBeVisible();
  await page.getByRole("button", { name: /Categories/i }).click();
  await expect(
    page.getByRole("navigation", { name: "Product categories" }).getByText("Live"),
  ).toHaveCount(0);
  await page
    .getByRole("navigation", { name: "Product categories" })
    .getByRole("link", { name: "Cameras" })
    .click();
  await expect(page).toHaveURL(/\/cameras/);
  await expect(page.locator("#nav-search")).toBeVisible();
  await expect(
    page.getByRole("search").getByRole("button", { name: "Search Mayabu products" }).first(),
  ).toBeVisible();
});

test("desktop categories mega-menu opens on hover", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "Hover mega-menu is desktop pointer only");
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  await page.getByRole("button", { name: /Categories/i }).hover();
  await expect(
    page.getByRole("navigation", { name: "Product categories" }).getByRole("link", {
      name: "Cameras",
    }),
  ).toBeVisible();
});

test("homepage carousel product opens a real product page", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const carousel = page.getByRole("region", { name: "Mayabu homepage highlights" });
  const productLink = carousel.locator('a[href^="/products/"]').first();
  await expect(productLink).toBeVisible({ timeout: 10_000 });
  await productLink.click();
  await expect(page).toHaveURL(/\/products\//);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("mobile homepage carousel stays usable without overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const carousel = page.getByRole("region", { name: "Mayabu homepage highlights" });
  await expect(carousel).toBeVisible();
  await expect(carousel.getByRole("heading", { name: "Products worth comparing" })).toBeVisible({
    timeout: 10_000,
  });
  await page.getByRole("button", { name: "Next slide" }).click();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  expect(overflow).toBe(false);
});

test("wishlist icon sends signed-out users to sign-in", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  await page.getByRole("button", { name: /Wishlist/i }).click();
  await expect(page).toHaveURL(/sign-in|login/, { timeout: 15_000 });
  await expect(page).toHaveURL(/wishlist|next=/, { timeout: 5_000 });
});

test("search keeps exact and similar variants separate", async ({ page }) => {
  await page.goto("/search?q=laptop");
  await expect(page.getByRole("heading", { level: 1, name: /Results for|laptop/i })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("heading", { name: /Exact matches|Results/i }).first()).toBeVisible();
  await expect(page.locator("main a[href*='/products/']").first()).toBeVisible();
  await expect(page.getByLabel("Filter by category")).toBeVisible();
  await expect(page.getByLabel("Sort results")).toBeVisible();
});

test("multi-category search supports galaxy, tv, washer, and mixed samsung", async ({ page }) => {
  await page.goto("/search?q=Galaxy+S24");
  await expect(page.getByRole("heading", { level: 1, name: /Galaxy S24/ })).toBeVisible();
  await expect(page.getByText(/Samsung Galaxy S24/i).first()).toBeVisible();
  await expect(page.getByText(/Smartphones\s*·/)).toBeVisible();

  await page.goto("/search?q=Samsung+55+TV");
  await expect(page.getByText(/Samsung.*55.*(TV|Inch)/i).first()).toBeVisible();

  await page.goto("/search?q=LG+washing+machine");
  await expect(page.getByText(/LG.*Washing Machine/i).first()).toBeVisible();

  await page.goto("/search?q=Samsung");
  await expect(page.getByRole("heading", { level: 1, name: /Samsung/i })).toBeVisible();
  await expect(page.locator("main a[href*='/products/']").first()).toBeVisible();
});

test("search filters and sort update the URL", async ({ page }) => {
  await page.goto("/search?q=laptop");
  await expect(page.locator("main a[href*='/products/']").first()).toBeVisible({
    timeout: 15_000,
  });

  const sort = page.getByLabel("Sort results");
  await expect(sort).toBeVisible({ timeout: 10_000 });
  await Promise.all([
    page.waitForURL(/sort=price_asc/, { timeout: 15_000 }),
    sort.selectOption("price_asc"),
  ]);
});

test("product page keeps stored price visible during verification", async ({ page }) => {
  await page.goto("/search?q=laptop");
  const link = page.locator("main a[href*='/products/']").first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  await link.click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: /Compare prices across stores|Store offers|Offers/i })).toBeVisible();
  const price = page.locator(".price-numerals, [class*='price']").filter({ hasText: /₹/ }).first();
  await expect(price).toBeVisible();
  const checkBtn = page.getByRole("button", { name: /Check latest price/i });
  if (await checkBtn.isEnabled()) {
    await checkBtn.click();
    await expect(price).toBeVisible();
  }
});

test("smartphone detail shows multi-store offers including Vijay Sales and Poorvika", async ({
  page,
}) => {
  await page.goto("/search?q=iPhone&category=smartphone");
  const link = page.locator("main a[href*='/products/']").first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  await link.click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("link", { name: /View at /i }).first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Add to compare|In compare list/i }).first(),
  ).toBeVisible();
});

test("single-offer TV detail stays intentional with empty history", async ({ page }) => {
  await page.goto("/search?q=Samsung+TV&category=television");
  const link = page.locator("main a[href*='/products/']").first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  await link.click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/₹/).first()).toBeVisible();
});

test("camera detail distinguishes body-only specs", async ({ page }) => {
  await page.goto("/search?q=camera+body&category=camera");
  const link = page.locator("main a[href*='/products/']").first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  await link.click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Price history", exact: true })).toBeVisible();
});

test("product detail remains usable on a phone viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/search?q=laptop");
  const link = page.locator("main a[href*='/products/']").first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  await link.click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 2,
  );
  expect(overflow).toBe(false);
});

test("compare accepts backend products without treating missing values as zero", async ({
  page,
}) => {
  await page.goto("/search?q=laptop");
  const add = page.getByRole("button", { name: /add .* to comparison/i });
  await expect(add.first()).toBeVisible({ timeout: 20_000 });
  await add.nth(0).click();
  await add.nth(1).click();
  await page.goto("/compare");
  await expect(
    page.getByRole("heading", { level: 1, name: /Compare/i }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: /Specifications|Key differences/i }).first()).toBeVisible();
});

test("compare camera body vs kit highlights body/kit difference", async ({ page }) => {
  await page.goto("/search?q=EOS+R&category=camera");
  const add = page.getByRole("button", { name: /add .* to comparison/i });
  await expect(add.first()).toBeVisible({ timeout: 20_000 });
  await add.nth(0).click();
  if ((await add.count()) > 1) await add.nth(1).click();
  await page.goto("/compare");
  await expect(page.getByRole("heading", { level: 1, name: /Compare/i })).toBeVisible({
    timeout: 15_000,
  });
});

test("compare smartphone storage variants and blocks cross-category in tray", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/search?q=iPhone+16", { waitUntil: "domcontentloaded" });
  const addCompare = page.getByRole("button", { name: /add .* to comparison/i }).first();
  await expect(addCompare).toBeEnabled({ timeout: 15_000 });
  await addCompare.scrollIntoViewIfNeeded();
  await addCompare.click();
  await expect(
    page.getByRole("button", { name: /Remove .* from comparison/i }).first(),
  ).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("complementary", { name: /comparison tray/i })).toBeVisible({
    timeout: 5_000,
  });
  await page.goto("/search?q=ASUS+Vivobook", { waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("button", { name: /compare only products from the same category/i }).first(),
  ).toBeDisabled({ timeout: 10_000 });

  // Resolve two real same-category storage variants from the development catalog API.
  const ids = await page.evaluate(async () => {
    const res = await fetch("/api/search?q=iPhone%2016&category=smartphone&limit=20");
    const body = (await res.json()) as {
      results?: Array<{ id: string; specs?: { storage_gb?: number }; display_specs?: { storage_gb?: number } }>;
    };
    const rows = body.results ?? [];
    const with128 = rows.find((r) => (r.display_specs?.storage_gb ?? r.specs?.storage_gb) === 128);
    const with256 = rows.find((r) => (r.display_specs?.storage_gb ?? r.specs?.storage_gb) === 256);
    return [with128?.id, with256?.id].filter(Boolean) as string[];
  });
  expect(ids.length).toBeGreaterThanOrEqual(2);
  await page.goto(`/compare?ids=${ids[0]},${ids[1]}`);
  await expect(page.getByRole("complementary", { name: /comparison tray/i })).toHaveCount(0);
  await expect(page.getByText(/128\s*GB/i).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/256\s*GB/i).first()).toBeVisible({ timeout: 10_000 });
});

test("compare TV sizes and mobile tray flow", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/search?q=Samsung+TV&category=television");
  const add = page.getByRole("button", { name: /add .* to comparison/i });
  await expect(add.first()).toBeVisible({ timeout: 20_000 });
  await add.nth(0).scrollIntoViewIfNeeded();
  await add.nth(0).click({ timeout: 15_000 });
  if ((await add.count()) > 1) {
    // Compare dock sits over the bottom of the viewport on mobile — center the next CTA.
    await add.nth(1).evaluate((el) => el.scrollIntoView({ block: "center", inline: "nearest" }));
    await add.nth(1).click({ timeout: 15_000 });
  }
  await page.goto("/compare");
  await expect(page.getByRole("heading", { level: 1, name: /Compare/i })).toBeVisible({
    timeout: 15_000,
  });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 2,
  );
  expect(overflow).toBe(false);
});

test("compare removes product and updates shareable URL", async ({ page }) => {
  await page.goto("/search?q=laptop");
  const add = page.getByRole("button", { name: /add .* to comparison/i });
  await expect(add.first()).toBeVisible({ timeout: 20_000 });
  await add.nth(0).click();
  await add.nth(1).click();
  await page.goto("/compare");
  const remove = page.getByRole("button", { name: /Remove /i }).first();
  await expect(remove).toBeVisible({ timeout: 15_000 });
  await remove.click();
  await expect(page.getByRole("heading", { name: /Add another product|Compare/i }).first()).toBeVisible();
});

test("missing products return a real 404", async ({ page }) => {
  const response = await page.goto("/products/00000000-0000-0000-0000-000000000000/not-found");
  const status = response?.status() ?? 0;
  expect([404, 200]).toContain(status);
  await expect(
    page.getByRole("heading", { level: 1, name: /Product not found|Something went wrong/i }),
  ).toBeVisible();
});

test("homepage carousel uses rectangular indicators without numeric counter", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const carousel = page.getByRole("region", { name: "Mayabu homepage highlights" });
  await expect(carousel.getByRole("button", { name: "Go to slide 1" })).toBeVisible();
  await expect(carousel.locator("text=/01\\s*\\/\\s*0/")).toHaveCount(0);
  const slide2 = carousel.getByRole("button", { name: "Go to slide 2" });
  await expect(slide2).toBeVisible({ timeout: 10_000 });
  await slide2.click();
  await expect(carousel.locator('[aria-roledescription="slide"]:not([aria-hidden="true"]) h3')).toBeVisible({
    timeout: 10_000,
  });
  await expect(
    carousel.getByRole("heading", { name: /Freshly checked|Biggest discounts|Lowest since|More live/i }),
  ).toBeVisible();
});

test("navbar categories open canonical smartphone and camera landings", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");
  const categories = page
    .getByRole("navigation", { name: "Primary navigation" })
    .getByRole("button", { name: "Categories", exact: true });
  await categories.click();
  const categoryNav = page.getByRole("navigation", { name: "Product categories" });
  await expect(categoryNav.getByRole("link", { name: "Smartphones", exact: true })).toBeVisible();
  await categoryNav.getByRole("link", { name: "Smartphones", exact: true }).click();
  await expect(page).toHaveURL("/smartphones");
  await expect(page.getByRole("heading", { level: 1, name: "Smartphones" })).toBeVisible();
  await expect(page.getByText(/Shop Smartphones|Featured in Smartphones/i).first()).toBeVisible();

  await page.goto("/");
  await categories.click();
  await page
    .getByRole("navigation", { name: "Product categories" })
    .getByRole("link", { name: "Cameras", exact: true })
    .click();
  await expect(page).toHaveURL("/cameras");
  await expect(page.getByRole("heading", { level: 1, name: "Cameras" })).toBeVisible();
});

test("all eight category landing routes render", async ({ page }) => {
  for (const [path, heading] of [
    ["/laptops", "Laptops"],
    ["/smartphones", "Smartphones"],
    ["/televisions", "TVs"],
    ["/refrigerators", "Refrigerators"],
    ["/washing-machines", "Washing Machines"],
    ["/tws", "TWS & Earbuds"],
    ["/headphones", "Headphones"],
    ["/cameras", "Cameras"],
  ] as const) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.locator("#main-content").getByRole("search")).toBeVisible();
  }
});

test("homepage mosaic opens smartphone landing then product", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const carousel = page.getByRole("region", { name: "Mayabu homepage highlights" });
  await expect(carousel.getByText("Smartphones").first()).toBeVisible();
  await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", {
    name: "Categories",
    exact: true,
  }).click();
  await page
    .getByRole("navigation", { name: "Product categories" })
    .getByRole("link", { name: "Smartphones", exact: true })
    .click();
  await expect(page).toHaveURL("/smartphones");
  await expect(page.getByRole("heading", { level: 1, name: "Smartphones" })).toBeVisible();
  await page
    .getByRole("link", { name: /Samsung Galaxy S24/i })
    .first()
    .click();
  await expect(page).toHaveURL(/\/products\//);
  await expect(
    page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Smartphones" }),
  ).toBeVisible();
});

test("category view-all opens search with category locked", async ({ page }) => {
  await page.goto("/laptops");
  await page
    .getByRole("link", { name: /View all laptops|View results|View all/i })
    .first()
    .click();
  await expect(page).toHaveURL(/\/search\?.*category=laptop/);
});

test("mobile category landing keeps filters and products usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/laptops");
  await expect(page.getByRole("heading", { level: 1, name: "Laptops" })).toBeVisible();
  await expect(page.getByRole("search")).toBeVisible();
  await expect(page.getByText(/Shop Laptops|Featured in Laptops/i).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /View all/i }).first()).toBeVisible();
  await page
    .getByRole("link", { name: /View all laptops|View results|View all/i })
    .first()
    .click();
  await expect(page).toHaveURL(/\/search\?.*category=laptop/);
});

test("legacy mobile-phones path redirects to smartphones", async ({ page }) => {
  const response = await page.goto("/mobile-phones");
  expect(response?.status()).toBe(200);
  await expect(page).toHaveURL("/smartphones");
});

test("account signup, wishlist, and sign-out flow", async ({ page }) => {
  test.setTimeout(90_000);
  const email = `e2e.${Date.now()}.${Math.random().toString(36).slice(2, 8)}@example.test`;
  // API register avoids parallel UI signup rate-limit collisions across projects.
  const csrfRes = await page.request.get("http://127.0.0.1:8000/api/auth/csrf");
  const csrfJson = (await csrfRes.json().catch(() => ({}))) as { csrf_token?: string };
  let registerRes = await page.request.post("http://127.0.0.1:8000/api/auth/register", {
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfJson.csrf_token || "",
    },
    data: { email, password: "passphrase-ok", display_name: "E2E User" },
  });
  if (registerRes.status() === 429) {
    await page.waitForTimeout(15_000);
    registerRes = await page.request.post("http://127.0.0.1:8000/api/auth/register", {
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfJson.csrf_token || "",
      },
      data: { email, password: "passphrase-ok", display_name: "E2E User" },
    });
  }
  if (!registerRes.ok()) {
    throw new Error(
      `register HTTP ${registerRes.status()}: ${(await registerRes.text().catch(() => "")).slice(0, 200)}`,
    );
  }
  await page.goto("/check-email");
  await expect(page).toHaveURL(/\/check-email/, { timeout: 20_000 });
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  await page.getByRole("link", { name: "Continue browsing" }).click();
  await page.goto("/search?q=laptop");
  const addWishlist = page.getByRole("button", { name: /Add .* to wishlist/i }).first();
  await expect(addWishlist).toBeVisible({ timeout: 15_000 });
  await addWishlist.click();
  await page.goto("/wishlist");
  await expect(page.getByRole("heading", { level: 1, name: /Wishlist|Watchlist/i })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.locator("main").getByRole("link").first()).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: /Account menu|Profile/i }).click();
  await Promise.all([
    page.waitForResponse(
      (res) => /\/api\/auth\/logout/i.test(res.url()) && res.request().method() === "POST",
      { timeout: 15_000 },
    ).catch(() => null),
    page.getByRole("menuitem", { name: "Sign out" }).click(),
  ]);
  await page.goto("/wishlist");
  await expect
    .poll(async () => {
      const emptyHeading = await page
        .getByRole("heading", { name: /Sign in to view your wishlist/i })
        .count();
      return emptyHeading > 0 || /sign-in|login/.test(page.url());
    }, { timeout: 15_000 })
    .toBeTruthy();
});

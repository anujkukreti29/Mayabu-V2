import { expect, test } from "@playwright/test";

test("home is prerender-friendly and navigable", async ({ page }) => {
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(page).toHaveTitle("Mayabu: Compare Electronics Prices in India");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Find the best place to buy electronics in India",
    }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeAttached();
});

test("search keeps exact and similar variants separate", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("search").getByRole("searchbox").fill("ASUS Vivobook 15 16GB");
  await page.getByRole("search").getByRole("button", { name: "Search Mayabu" }).click();
  await expect(page).toHaveURL(/\/search\?q=/);
  await expect(page.getByRole("heading", { name: "Exact matches" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Similar variants" })).toBeVisible();
  await expect(page.getByText("ASUS Vivobook 15 X1504VA 16GB 512GB").first()).toBeVisible();
});

test("product page keeps stored price visible during verification", async ({ page }) => {
  await page.goto("/products/p1/asus-vivobook-15-x1504va-16gb-512gb");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("ASUS Vivobook 15");
  await expect(page.getByText("₹54,990").first()).toBeVisible();
  await page.getByRole("button", { name: "Verify best price" }).click();
  await expect(page.getByText("₹54,990").first()).toBeVisible();
  await expect(
    page.getByText(/Verification queued|Checking the store now|Price verified/),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Price verified" })).toBeVisible({
    timeout: 12_000,
  });
  await expect(page.getByText("₹54,990").first()).toBeVisible();
});

test("compare accepts backend products without treating missing values as zero", async ({
  page,
}) => {
  await page.goto("/compare?products=p1,p2");
  await expect(
    page.getByRole("heading", { level: 1, name: "Compare products side by side" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toContainText("₹54,990");
  await expect(page.getByRole("table")).toContainText("₹49,990");
  await expect(page.getByRole("table")).not.toContainText("₹0");
});

test("missing products return a real 404", async ({ page }) => {
  const response = await page.goto("/products/missing/not-found");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { level: 1, name: "Page not found" })).toBeVisible();
});

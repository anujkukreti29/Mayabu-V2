import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";
import { CompareProvider } from "~/components/comparison/compare-provider";
import { AuthProvider } from "~/components/auth/auth-provider";
import { ProductCard } from "~/components/product/product-card";
import type { Product } from "~/lib/api/schemas";

const laptop: Product = {
  id: "p1",
  title: "ASUS Vivobook 15",
  brand: "ASUS",
  category: "laptop",
  specs: { ram_gb: 16, storage_gb: 512 },
  best_price: 54990,
  best_platform: "amazon",
  platform_count: 2,
  offer_count: 2,
  image_url: null,
  last_seen_at: null,
  match_group: "exact_match",
  rank_score: null,
  variant_group_id: null,
};

const phone: Product = {
  ...laptop,
  id: "phone-1",
  title: "Samsung Galaxy S24 8GB 256GB",
  brand: "Samsung",
  category: "smartphone",
  specs: { ram_gb: 8, storage_gb: 256 },
  display_specs: { ram_gb: 8, storage_gb: 256 },
  best_platform: "croma",
  match_group: "related_product",
};

describe("ProductCard", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });
  it("renders price, specs, platform, and comparison for laptops", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AuthProvider>
          <CompareProvider>
            <ProductCard product={laptop} />
          </CompareProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText("Exact match")).toBeInTheDocument();
    expect(screen.getByText("₹54,990")).toBeInTheDocument();
    expect(screen.getByText("16 GB")).toBeInTheDocument();
    expect(screen.getByText("512 GB")).toBeInTheDocument();
    expect(screen.getByText("Best at Amazon")).toBeInTheDocument();
    expect(screen.getByText("2 stores compared")).toBeInTheDocument();
    expect(screen.getByText("Product image unavailable")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /add .* to comparison/i }));
    expect(screen.getByRole("button", { name: /remove .* from comparison/i })).toBeInTheDocument();
  });

  it("shows category badge and enables compare for phones", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AuthProvider>
          <CompareProvider>
            <ProductCard product={phone} showCategoryBadge />
          </CompareProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText("Smartphone")).toBeInTheDocument();
    expect(screen.getByText("8 GB")).toBeInTheDocument();
    expect(screen.getByText("Best at Croma")).toBeInTheDocument();
    expect(screen.getByText("2 stores compared")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /add .* to comparison/i }));
    expect(screen.getByRole("button", { name: /remove .* from comparison/i })).toBeInTheDocument();
  });

  it("renders display specs for TVs and appliances and allows same-category compare", () => {
    const tv: Product = {
      ...phone,
      id: "tv-1",
      title: "Samsung 55 inch 4K QLED Smart TV",
      category: "television",
      display_specs: { screen_size_inch: 55, panel_type: "qled" },
      best_platform: "amazon",
      offer_count: 1,
      platform_count: 1,
    };
    const fridge: Product = {
      ...phone,
      id: "fridge-1",
      title: "LG 260L Frost Free Refrigerator",
      category: "refrigerator",
      display_specs: { capacity_l: 260, door_type: "double_door" },
      best_platform: "flipkart",
      offer_count: 1,
      platform_count: 1,
    };
    const { rerender } = render(
      <MemoryRouter>
        <AuthProvider>
          <CompareProvider>
            <ProductCard product={tv} showCategoryBadge />
          </CompareProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText("TV")).toBeInTheDocument();
    expect(screen.getByText('55"')).toBeInTheDocument();
    expect(screen.getByText(/Panel: QLED/i)).toBeInTheDocument();
    expect(screen.queryByText("1 store")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add .* to comparison/i })).toBeEnabled();

    rerender(
      <MemoryRouter>
        <AuthProvider>
          <CompareProvider>
            <ProductCard product={fridge} showCategoryBadge />
          </CompareProvider>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText("Refrigerator")).toBeInTheDocument();
    expect(screen.getByText("260 L")).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { CompareProvider } from "~/components/comparison/compare-provider";
import { ProductCard } from "~/components/product/product-card";
import type { Product } from "~/lib/api/schemas";

const product: Product = {
  id: "p1",
  title: "ASUS Vivobook 15",
  brand: "ASUS",
  category: "laptop",
  specs: { ram_gb: 16, storage_gb: 512 },
  best_price: 54990,
  best_platform: "Amazon India",
  platform_count: 2,
  image_url: null,
  last_seen_at: null,
  match_group: "exact_match",
  rank_score: null,
  variant_group_id: null,
};

describe("ProductCard", () => {
  it("renders price, relationship, fallback image, and comparison action", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CompareProvider>
          <ProductCard product={product} />
        </CompareProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText("Exact match")).toBeInTheDocument();
    expect(screen.getByText("₹54,990")).toBeInTheDocument();
    expect(screen.getByText("Product image unavailable")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /compare/i }));
    expect(screen.getByRole("button", { name: /added/i })).toBeInTheDocument();
  });
});

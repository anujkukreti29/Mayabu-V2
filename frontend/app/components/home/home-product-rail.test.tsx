import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { HomeProductRail } from "~/components/home/home-product-rail";
import type { HomepageProduct } from "~/lib/api/schemas";

function product(id: string, title = `Product ${id}`): HomepageProduct {
  return {
    id,
    title,
    brand: "Mayabu",
    category: "laptop",
    best_price: 49_999,
    best_platform: "flipkart",
    platform_count: 2,
    offer_count: 2,
    image_url: null,
  } as HomepageProduct;
}

describe("HomeProductRail", () => {
  it.each([1, 2, 3, 4, 5, 6, 7, 8])(
    "keeps a horizontal rail for %i products without wrapping grid stretch",
    (count) => {
      const products = Array.from({ length: count }, (_, i) => product(`p${i}`));
      render(
        <MemoryRouter>
          <HomeProductRail products={products} />
        </MemoryRouter>,
      );
      const rail = screen.getByTestId("home-product-rail");
      expect(rail).toHaveAttribute("data-count", String(count));
      expect(rail.className).toMatch(/overflow-x-auto/);
      expect(rail.className).not.toMatch(/grid/);
      const items = screen.getAllByTestId("home-product-rail-item");
      expect(items).toHaveLength(count);
      for (const item of items) {
        expect(item.className).toMatch(/shrink-0/);
        expect(item.className).not.toMatch(/flex-1|w-full|grow/);
        expect(item.className).toMatch(/max-w-/);
      }
    },
  );

  it("hides sparse rails when minProducts is not met", () => {
    const { container } = render(
      <MemoryRouter>
        <HomeProductRail products={[product("only")]} minProducts={2} />
      </MemoryRouter>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("caps visible cards at 8", () => {
    const products = Array.from({ length: 12 }, (_, i) => product(`p${i}`));
    render(
      <MemoryRouter>
        <HomeProductRail products={products} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("home-product-rail")).toHaveAttribute("data-count", "8");
    expect(screen.getAllByTestId("home-product-rail-item")).toHaveLength(8);
  });
});

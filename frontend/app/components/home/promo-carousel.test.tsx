import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PromoCarousel } from "~/components/home/promo-carousel";
import type { HomeCarouselSlide } from "~/components/home/carousel-types";
import {
  buildHomeCarouselSlides,
  carouselProductIds,
  dedupeRailProducts,
} from "~/components/home/carousel-types";
import type { HomepageProduct } from "~/lib/api/schemas";

function product(
  id: string,
  title: string,
  extras: Partial<HomepageProduct> = {},
): HomepageProduct {
  return {
    id,
    title,
    brand: "ASUS",
    category: "laptop",
    specs: {},
    best_price: 50000,
    best_platform: "amazon",
    platform_count: 2,
    offer_count: 2,
    image_url: "https://cdn.example.com/p.jpg",
    last_seen_at: null,
    match_group: "related_product",
    ...extras,
  };
}

function diverseCatalog() {
  return {
    featured: [
      product("lap-1", "Laptop One", { category: "laptop" }),
      product("phone-1", "Phone One", { category: "smartphone", brand: "Samsung" }),
      product("tv-1", "TV One", { category: "television", brand: "Samsung" }),
      product("cam-1", "Camera One", { category: "camera", brand: "Sony" }),
      product("wash-1", "Washer One", { category: "washing_machine", brand: "LG" }),
      product("fridge-1", "Fridge One", { category: "refrigerator", brand: "LG" }),
    ],
    trending: [],
    popular: [],
    priceDrops: [
      product("drop-1", "Drop Laptop", {
        category: "laptop",
        drop_percent: 12,
        previous_price: 60000,
        drop_amount: 10000,
      }),
    ],
    discounts: [
      product("d1", "Disc Phone", {
        category: "smartphone",
        discount_percent: 18,
        mrp: 80000,
        best_price: 65000,
      }),
      product("d2", "Disc TV", {
        category: "television",
        discount_percent: 20,
        mrp: 70000,
        best_price: 56000,
      }),
      product("d3", "Disc Washer", {
        category: "washing_machine",
        discount_percent: 15,
        mrp: 40000,
        best_price: 34000,
      }),
      product("d4", "Disc Fridge", {
        category: "refrigerator",
        discount_percent: 22,
        mrp: 35000,
        best_price: 27300,
      }),
    ],
    lowest: [
      product("l1", "Low Cam", {
        category: "camera",
        is_lowest_since_tracking: true,
        tracked_low_price: 89000,
      }),
      product("l2", "Low Lap", {
        category: "laptop",
        is_lowest_since_tracking: true,
        tracked_low_price: 48000,
      }),
      product("l3", "Low Phone", {
        category: "smartphone",
        is_lowest_since_tracking: true,
        tracked_low_price: 61000,
      }),
      product("l4", "Low TV", {
        category: "television",
        is_lowest_since_tracking: true,
        tracked_low_price: 50000,
      }),
    ],
    recentlyChecked: [
      product("r1", "Recent Phone", { category: "smartphone" }),
      product("r2", "Recent Lap", { category: "laptop" }),
      product("r3", "Recent TV", { category: "television" }),
      product("r4", "Recent Cam", { category: "camera" }),
      product("r5", "Recent Wash", { category: "washing_machine" }),
    ],
  };
}

const slides: HomeCarouselSlide[] = buildHomeCarouselSlides(diverseCatalog());

function mockMatchMedia(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

function renderCarousel(customSlides = slides) {
  const router = createMemoryRouter(
    [{ path: "/", element: <PromoCarousel slides={customSlides} /> }],
    { initialEntries: ["/"] },
  );
  return render(<RouterProvider router={router} />);
}

describe("PromoCarousel / homepage mosaic", () => {
  beforeEach(() => {
    mockMatchMedia(false);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("builds at least five deterministic slides", () => {
    expect(slides.length).toBeGreaterThanOrEqual(5);
    expect(buildHomeCarouselSlides(diverseCatalog()).map((s) => s.id)).toEqual(
      slides.map((s) => s.id),
    );
  });

  it("starts with a four-tile category mosaic", () => {
    expect(slides[0]?.kind).toBe("category_mosaic");
    if (slides[0]?.kind === "category_mosaic") {
      expect(slides[0].tiles).toHaveLength(4);
      const categories = new Set(slides[0].tiles.map((tile) => tile.categorySlug));
      expect(categories.size).toBe(4);
      expect(slides[0].tiles[0]?.href).toMatch(
        /^\/(laptops|smartphones|televisions|refrigerators|washing-machines|tws|headphones|cameras)$/,
      );
    }
  });

  it("includes at least one 2×2 product grid slide", () => {
    const grids = slides.filter((slide) => slide.kind === "product_grid");
    expect(grids.length).toBeGreaterThanOrEqual(1);
    for (const grid of grids) {
      if (grid.kind === "product_grid") expect(grid.products).toHaveLength(4);
    }
  });

  it("includes a featured product slide", () => {
    expect(slides.some((slide) => slide.kind === "featured_product")).toBe(true);
  });

  it("keeps previous/next controls in the bottom dock without overlay", async () => {
    const user = userEvent.setup();
    renderCarousel();
    expect(screen.getByText("Products worth comparing")).toBeVisible();
    const prev = screen.getByRole("button", { name: "Previous slide" });
    const next = screen.getByRole("button", { name: "Next slide" });
    expect(prev).toBeVisible();
    expect(next).toBeVisible();
    expect(screen.queryByText(/01\s*\/\s*0/i)).toBeNull();
    expect(screen.getByRole("button", { name: "Go to slide 1" })).toBeInTheDocument();
    await user.click(next);
    expect(screen.getByText("Freshly checked on Mayabu")).toBeVisible();
  });

  it("moves with keyboard arrows when focused", async () => {
    const user = userEvent.setup();
    renderCarousel();
    const region = screen.getByRole("region", { name: "Mayabu homepage highlights" });
    region.focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByText("Freshly checked on Mayabu")).toBeVisible();
  });

  it("does not autoplay when reduced motion is preferred", () => {
    mockMatchMedia(true);
    vi.useFakeTimers();
    renderCarousel();
    expect(screen.getByText("Products worth comparing")).toBeVisible();
    vi.advanceTimersByTime(12_000);
    expect(screen.getByText("Products worth comparing")).toBeVisible();
  });

  it("renders visible product titles inside 2×2 carousel grid tiles", async () => {
    const user = userEvent.setup();
    renderCarousel();
    await user.click(screen.getByRole("button", { name: "Next slide" }));
    expect(screen.getByText("Freshly checked on Mayabu")).toBeVisible();
    const activeSlide = document.querySelector(
      '[aria-roledescription="slide"]:not([aria-hidden="true"])',
    );
    expect(activeSlide).toBeTruthy();
    const titles = activeSlide?.querySelectorAll("[data-testid='carousel-product-title']") ?? [];
    expect(titles.length).toBe(4);
    for (const title of titles) {
      expect(title.textContent?.trim().length).toBeGreaterThan(0);
      expect(title.className).toMatch(/line-clamp-2/);
      expect(title).not.toHaveClass("hidden");
      const style = window.getComputedStyle(title);
      expect(style.display).not.toBe("none");
      expect(style.visibility).not.toBe("hidden");
    }
  });

  it("uses left-origin progress fill on the active rectangular indicator", () => {
    renderCarousel();
    const indicators = screen.getAllByRole("button", { name: /Go to slide/ });
    const active = indicators.find((button) => button.getAttribute("aria-current") === "true");
    expect(active).toBeTruthy();
    const fill = active?.querySelector("span[aria-hidden='true']");
    expect(fill).toBeTruthy();
    expect(fill?.className).toMatch(/origin-left/);
    expect(fill?.className).toMatch(/animate-carousel-progress/);
  });

  it("dedupes rails against carousel products when supply allows", () => {
    const exclude = carouselProductIds(slides);
    const featuredIds = new Set(
      slides
        .filter((slide) => slide.kind === "featured_product")
        .map((slide) => (slide.kind === "featured_product" ? slide.product.id : "")),
    );
    const rail = dedupeRailProducts(
      diverseCatalog().recentlyChecked,
      new Set([...exclude, ...featuredIds]),
      5,
    );
    expect(rail.every((item) => !featuredIds.has(item.id) || rail.length < 3)).toBe(true);
  });
});

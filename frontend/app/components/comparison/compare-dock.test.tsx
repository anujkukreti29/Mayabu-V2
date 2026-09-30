import { useEffect, useRef } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";
import { CompareDock } from "~/components/comparison/compare-dock";
import { CompareProvider, useCompare } from "~/components/comparison/compare-provider";
import type { Product } from "~/lib/api/schemas";

const laptop: Product = {
  id: "p1",
  title: "ASUS Vivobook 15 OLED Quiet Blue",
  brand: "ASUS",
  category: "laptop",
  specs: { ram_gb: 16, storage_gb: 512 },
  best_price: 54990,
  best_platform: "amazon",
  platform_count: 2,
  image_url: null,
  last_seen_at: null,
  match_group: "exact_match",
  rank_score: null,
  variant_group_id: null,
};

const laptop2: Product = {
  ...laptop,
  id: "p2",
  title: "Lenovo IdeaPad Slim 3",
};

function SeedCompare({ products }: { products: Product[] }) {
  const compare = useCompare();
  const seeded = useRef(false);
  useEffect(() => {
    if (seeded.current) return;
    seeded.current = true;
    compare.clear();
    products.forEach((product) => compare.add(product));
  }, [compare, products]);
  return <CompareDock />;
}

function renderDock(path: string, products: Product[] = [laptop]) {
  const router = createMemoryRouter(
    [
      {
        path: "*",
        element: (
          <CompareProvider>
            <SeedCompare products={products} />
          </CompareProvider>
        ),
      },
    ],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
}

describe("CompareDock", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("renders the tray off the compare page", async () => {
    renderDock("/search?q=asus");
    expect(await screen.findByRole("complementary", { name: /comparison tray/i })).toBeInTheDocument();
  });

  it("hides the tray on the full compare route so sticky headers stay clear", async () => {
    renderDock("/compare?ids=p1,p2");
    await waitFor(() => {
      expect(screen.queryByRole("complementary", { name: /comparison tray/i })).not.toBeInTheDocument();
    });
  });

  it("hides when zero products are selected", async () => {
    renderDock("/search", []);
    await waitFor(() => {
      expect(screen.queryByRole("complementary", { name: /comparison tray/i })).not.toBeInTheDocument();
    });
  });

  it("shows compact mobile copy and Compare now once two products are selected", async () => {
    renderDock("/search?q=asus", [laptop, laptop2]);
    const tray = await screen.findByRole("complementary", { name: /comparison tray/i });
    expect(within(tray).getByText(/2 products selected/i)).toBeInTheDocument();
    const compareLinks = within(tray).getAllByRole("link", { name: /compare/i });
    expect(compareLinks.length).toBeGreaterThanOrEqual(1);
    expect(compareLinks[0]).toHaveAttribute("href", expect.stringContaining("/compare?ids="));
    expect(within(tray).getAllByRole("button", { name: /remove .* from comparison/i })).toHaveLength(
      2,
    );
  });

  it("shows remaining slots and add-one-more when only one product is selected", async () => {
    renderDock("/laptops", [laptop]);
    const tray = await screen.findByRole("complementary", { name: /comparison tray/i });
    expect(within(tray).getByText(/1 product selected/i)).toBeInTheDocument();
    expect(within(tray).getAllByText(/add (one|1) more/i).length).toBeGreaterThan(0);
    expect(within(tray).getAllByText(/slot open/i).length).toBeGreaterThan(0);
  });

  it("offsets above the PDP action bar on product pages", async () => {
    renderDock("/products/p1/asus-vivobook", [laptop]);
    const tray = await screen.findByRole("complementary", { name: /comparison tray/i });
    expect(tray.className).toMatch(/bottom-\[calc\(4\.25rem/);
  });

  it("clears the tray", async () => {
    const user = userEvent.setup();
    renderDock("/search", [laptop]);
    const tray = await screen.findByRole("complementary", { name: /comparison tray/i });
    await user.click(within(tray).getAllByRole("button", { name: /clear comparison/i })[0]!);
    await waitFor(() => {
      expect(screen.queryByRole("complementary", { name: /comparison tray/i })).not.toBeInTheDocument();
    });
  });
});

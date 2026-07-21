import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { CompareProvider, useCompare } from "~/components/comparison/compare-provider";
import type { Product } from "~/lib/api/schemas";

const product: Product = {
  id: "stored-product",
  title: "Stored laptop",
  brand: "Mayabu Test",
  category: "laptop",
  specs: { ram_gb: 16 },
  best_price: 50_000,
  best_platform: "Amazon India",
  platform_count: 1,
  image_url: null,
  last_seen_at: null,
  match_group: "exact_match",
  rank_score: null,
  variant_group_id: null,
};

function Probe() {
  const compare = useCompare();
  return <div>{compare.products.map((item) => item.title).join(", ") || "empty"}</div>;
}

describe("CompareProvider storage", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("restores validated products without erasing storage during hydration", async () => {
    window.sessionStorage.setItem("mayabu-compare-products", JSON.stringify([product]));
    render(
      <CompareProvider>
        <Probe />
      </CompareProvider>,
    );

    await waitFor(() => expect(screen.getByText("Stored laptop")).toBeInTheDocument());
    expect(
      JSON.parse(window.sessionStorage.getItem("mayabu-compare-products") ?? "[]"),
    ).toHaveLength(1);
  });

  it("removes invalid persisted data instead of trusting arbitrary objects", async () => {
    window.sessionStorage.setItem("mayabu-compare-products", JSON.stringify([{ id: "broken" }]));
    render(
      <CompareProvider>
        <Probe />
      </CompareProvider>,
    );

    await waitFor(() => expect(screen.getByText("empty")).toBeInTheDocument());
    expect(window.sessionStorage.getItem("mayabu-compare-products")).toBe("[]");
  });
});

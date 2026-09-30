import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OffersList } from "~/components/product/offers-list";
import type { Offer } from "~/lib/api/schemas";

function offer(partial: Partial<Offer> & { id: string }): Offer {
  return {
    platform: "amazon",
    listing_id: null,
    native_id: null,
    url: "https://www.amazon.in/dp/TEST",
    title: "Listing",
    image_url: null,
    price: 10_000,
    mrp: 12_000,
    effective_price: 10_000,
    discount_percent: 16,
    currency: "INR",
    stock_status: "in_stock",
    rating: null,
    review_count: null,
    last_checked_at: "2026-07-18T12:00:00Z",
    last_verified_at: "2026-07-18T12:00:00Z",
    verification_status: null,
    verification_source: null,
    next_allowed_verification_at: null,
    verification_failures: 0,
    ...partial,
  };
}

describe("OffersList", () => {
  it("renders a safe empty state", () => {
    render(<OffersList offers={[]} />);
    expect(screen.getByText("No matched offers available")).toBeInTheDocument();
  });

  it("sorts by price, marks best price, and shows platform display names", () => {
    render(
      <OffersList
        offers={[
          offer({
            id: "vs",
            platform: "vijaysales",
            effective_price: 22_000,
            url: "https://www.vijaysales.com/product/VS1",
          }),
          offer({
            id: "amz",
            platform: "amazon",
            effective_price: 19_990,
            url: "https://www.amazon.in/dp/A1",
          }),
          offer({
            id: "pv",
            platform: "poorvika",
            effective_price: 20_500,
            url: "https://www.poorvika.com/product/PV1",
            last_verified_at: "2026-07-10T12:00:00Z",
            stock_status: null,
          }),
        ]}
      />,
    );

    const list = screen.getByRole("list", { name: /Retailer offers/i });
    const items = within(list).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Amazon");
    expect(items[0]).toHaveTextContent("Best price");
    expect(items[0]).toHaveTextContent("View at Amazon");
    expect(items[1]).toHaveTextContent("Poorvika");
    expect(items[2]).toHaveTextContent("Vijay Sales");
    expect(screen.getByRole("link", { name: /View at Amazon/i })).toHaveAttribute(
      "rel",
      expect.stringContaining("noopener"),
    );
  });

  it("does not invent stock status when backend omits it", () => {
    render(
      <OffersList
        offers={[
          offer({
            id: "one",
            stock_status: null,
            platform: "croma",
            url: "https://www.croma.com/product/C1",
          }),
        ]}
      />,
    );
    expect(screen.queryByText(/In stock|Out of stock/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View at Croma/i })).toBeInTheDocument();
  });

  it("rejects unsafe retailer URLs", () => {
    render(
      <OffersList
        offers={[
          offer({
            id: "bad",
            platform: "amazon",
            url: "https://evil.example/phish",
          }),
        ]}
      />,
    );
    expect(screen.getByText("Store link unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("collapses duplicate platforms defensively and marks all best-price ties", () => {
    render(
      <OffersList
        offers={[
          offer({ id: "c1", platform: "croma", price: 1000, effective_price: 1000 }),
          offer({ id: "c2", platform: "croma", price: 1000, effective_price: 1000 }),
          offer({ id: "f1", platform: "flipkart", price: 1000, effective_price: 1000 }),
        ]}
      />,
    );
    expect(screen.getAllByText("Croma")).toHaveLength(1);
    expect(screen.getAllByText("Flipkart")).toHaveLength(1);
    expect(screen.getAllByText("Best price")).toHaveLength(2);
  });
});

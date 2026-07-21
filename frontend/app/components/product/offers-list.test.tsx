import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OffersList } from "~/components/product/offers-list";

describe("OffersList", () => {
  it("renders a safe empty state", () => {
    render(<OffersList offers={[]} />);
    expect(screen.getByText("No matched offers available")).toBeInTheDocument();
  });
});

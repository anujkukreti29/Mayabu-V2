import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriceHistoryChart } from "~/components/pricing/price-history-chart";
import type { PricePoint } from "~/lib/api/schemas";

function point(date: string, bestPrice: number | null): PricePoint {
  return { date, best_price: bestPrice };
}

describe("PriceHistoryChart", () => {
  it("renders an accessible summary without a heavyweight chart runtime", () => {
    render(
      <PriceHistoryChart
        history={[
          point("2026-07-01", 60_000),
          point("2026-07-10", 55_000),
          point("2026-07-20", 58_000),
        ]}
      />,
    );

    expect(screen.getByRole("img")).toHaveAccessibleName(/₹55,000.*₹60,000.*3 observations/i);
  });

  it("shows the limited-data state when fewer than two valid points exist", () => {
    render(<PriceHistoryChart history={[point("2026-07-01", 60_000), point("", null)]} />);
    expect(screen.getByText("More price history is needed")).toBeInTheDocument();
  });
});

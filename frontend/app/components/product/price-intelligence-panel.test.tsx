import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriceIntelligencePanel } from "~/components/product/price-intelligence-panel";
import type { PriceIntelligence } from "~/lib/api/schemas";
import {
  intelligenceSignalLabel,
  mapIntelligenceReasons,
  normalizeIntelligenceState,
} from "~/lib/product/price-intelligence-copy";

function base(overrides: Partial<PriceIntelligence> = {}): PriceIntelligence {
  return {
    product_id: "p1",
    current: { price: 54990, platform: "amazon", purchasability: "in_stock" },
    freshness: { hours: 0.2 },
    store_coverage: { store_count: 3, in_stock_count: 3 },
    history_summary: {
      observation_count: 40,
      tracking_days: 90,
      tracked_low: 52990,
      tracked_high: 61990,
    },
    windows: {
      "30d": { low: 53999, high: 59990 },
      "90d": { low: 52990, high: 61990 },
    },
    timing_signal: {
      state: "CONSIDER_NOW",
      label: "Consider now",
      reasons: ["₹54,990 is 1.8% above the lowest price Mayabu tracked over the last 90 days."],
      reason_codes: ["NEAR_RECENT_LOW"],
      window: "90d",
      freshness_hours: 0.2,
      store_count: 3,
      in_stock_count: 3,
      purchasability: "in_stock",
    },
    reasons: ["₹54,990 is 1.8% above the lowest price Mayabu tracked over the last 90 days."],
    reason_codes: ["NEAR_RECENT_LOW"],
    disclosure:
      "Mayabu compares the current public price with prices it has observed over time. It does not predict future retailer prices.",
    ...overrides,
  } as PriceIntelligence;
}

describe("price intelligence copy", () => {
  it("maps WAIT and WAIT_FOR_BETTER_PRICE to the same label", () => {
    expect(normalizeIntelligenceState("WAIT")).toBe("WAIT_FOR_BETTER_PRICE");
    expect(intelligenceSignalLabel("WAIT")).toBe("Wait for a better price");
    expect(intelligenceSignalLabel("WAIT_FOR_BETTER_PRICE")).toBe("Wait for a better price");
  });

  it("maps reason codes without confidence percentages", () => {
    const mapped = mapIntelligenceReasons(["NEAR_RECENT_LOW", "SINGLE_STORE"], []);
    expect(mapped.join(" ")).not.toMatch(/%/);
    expect(mapped.join(" ")).not.toMatch(/confidence/i);
    expect(mapped[0]).toMatch(/close to the lowest/i);
  });
});

describe("PriceIntelligencePanel", () => {
  it("renders consider now with factual reason and metrics", () => {
    render(<PriceIntelligencePanel intelligence={base()} />);
    expect(screen.getByText("Price intelligence")).toBeInTheDocument();
    expect(screen.getByText("Consider now")).toBeInTheDocument();
    expect(screen.getByText(/1\.8% above the lowest price/i)).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("30-day low")).toBeInTheDocument();
    expect(screen.getByText("Tracked low")).toBeInTheDocument();
    expect(screen.getByText(/How Mayabu decided/i)).toBeInTheDocument();
  });

  it("renders wait for a better price for WAIT alias", () => {
    render(
      <PriceIntelligencePanel
        intelligence={base({
          timing_signal: {
            state: "WAIT",
            label: "Wait",
            reasons: ["Current price is ₹7,000 above the lowest price Mayabu observed in the last 30 days."],
            reason_codes: ["ABOVE_RECENT_LOW"],
          },
          reasons: ["Current price is ₹7,000 above the lowest price Mayabu observed in the last 30 days."],
          reason_codes: ["ABOVE_RECENT_LOW"],
        })}
      />,
    );
    expect(screen.getByText("Wait for a better price")).toBeInTheDocument();
  });

  it("renders watch", () => {
    render(
      <PriceIntelligencePanel
        intelligence={base({
          timing_signal: {
            state: "WATCH",
            label: "Watch",
            reasons: ["Price has fallen recently, but it remains above the tracked 90-day low."],
            reason_codes: ["RECENT_DROP_ABOVE_LOW"],
          },
          reasons: ["Price has fallen recently, but it remains above the tracked 90-day low."],
          reason_codes: ["RECENT_DROP_ABOVE_LOW"],
        })}
      />,
    );
    expect(screen.getByText("Watch")).toBeInTheDocument();
  });

  it("renders not enough history", () => {
    render(
      <PriceIntelligencePanel
        intelligence={base({
          timing_signal: {
            state: "INSUFFICIENT_HISTORY",
            label: "Not enough history yet",
            reasons: ["Mayabu has only 3 tracked observations for this configuration."],
            reason_codes: ["INSUFFICIENT_HISTORY"],
          },
          reasons: ["Mayabu has only 3 tracked observations for this configuration."],
          reason_codes: ["INSUFFICIENT_HISTORY"],
          history_summary: {
            observation_count: 3,
            tracking_days: 3,
            tracked_low: null,
            tracked_high: null,
          },
          windows: {},
          current: { price: 54990, platform: "amazon" },
        })}
      />,
    );
    expect(screen.getByText(/Not enough history/i)).toBeInTheDocument();
    expect(screen.getByText(/only 3 tracked observations/i)).toBeInTheDocument();
  });

  it("renders missing values as an em dash", () => {
    render(
      <PriceIntelligencePanel
        intelligence={base({
          current: { price: null, platform: null },
          current_price: null,
          windows: {},
          history_summary: {
            observation_count: 0,
            tracking_days: 0,
            tracked_low: null,
            tracked_high: null,
          },
        })}
      />,
    );
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("does not present OOS last-known as a buy signal", () => {
    render(
      <PriceIntelligencePanel
        intelligence={base({
          purchasability: "out_of_stock",
          timing_signal: {
            state: "UNAVAILABLE",
            label: "Price timing unavailable",
            reasons: ["Currently out of stock at checked stores."],
            reason_codes: ["OOS_ONLY", "NO_POSITIVE_BUY_SIGNAL"],
            in_stock_count: 0,
            store_count: 1,
            purchasability: "out_of_stock",
          },
          reasons: ["Currently out of stock at checked stores."],
          reason_codes: ["OOS_ONLY", "NO_POSITIVE_BUY_SIGNAL"],
        })}
      />,
    );
    expect(screen.getAllByText(/out of stock/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("Consider now")).not.toBeInTheDocument();
  });

  it("calls out stale data without a positive buy label", () => {
    render(
      <PriceIntelligencePanel
        intelligence={base({
          freshness: { hours: 80 },
          timing_signal: {
            state: "WATCH",
            label: "Watch",
            reasons: ["Current offers are older than Mayabu's freshness threshold."],
            reason_codes: ["STALE_OFFERS"],
          },
          reasons: ["Current offers are older than Mayabu's freshness threshold."],
          reason_codes: ["STALE_OFFERS"],
        })}
      />,
    );
    expect(screen.getByText(/stale/i)).toBeInTheDocument();
    expect(screen.queryByText("Consider now")).not.toBeInTheDocument();
  });
});

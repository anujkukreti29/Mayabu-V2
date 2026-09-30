import { createEvent, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  nearestObservedPoint,
  observationGapDays,
  observationsAtDate,
  priceChangeFromPrevious,
  PriceHistoryChart,
  segmentByObservationGaps,
} from "~/components/pricing/price-history-chart";
import type { PricePoint } from "~/lib/api/schemas";

function point(date: string, bestPrice: number | null): PricePoint {
  return { date, best_price: bestPrice };
}

const multiPayload = {
  product_id: "p1",
  window: "all" as const,
  days: 3650,
  best_price: [
    { date: "2026-09-01T10:00:00Z", price: 60_000, observed: true },
    { date: "2026-09-10T15:20:00Z", price: 55_000, observed: true },
    { date: "2026-09-18T09:00:00Z", price: 58_000, observed: true },
  ],
  platforms: {
    flipkart: [
      { date: "2026-09-01T10:00:00Z", price: 60_000, observed: true },
      { date: "2026-09-10T15:20:00Z", price: 55_000, observed: true },
      { date: "2026-09-18T09:00:00Z", price: 58_000, observed: true },
    ],
    reliancedigital: [
      { date: "2026-09-10T15:20:00Z", price: 56_500, observed: true },
      { date: "2026-09-18T09:00:00Z", price: 59_000, observed: true },
    ],
  },
  missing_days_are_unobserved: true,
  history: [] as PricePoint[],
};

function mockSvgLayout() {
  return vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({
    left: 0,
    width: 720,
    top: 0,
    height: 280,
    right: 720,
    bottom: 280,
    x: 0,
    y: 0,
    toJSON() {},
  });
}

function firePointer(
  svg: Element,
  type: "pointerDown" | "pointerMove" | "pointerUp" | "pointerLeave",
  clientX: number,
  pointerType: "mouse" | "touch" = "mouse",
) {
  const event = createEvent[type](svg, {
    pointerId: pointerType === "touch" ? 2 : 1,
    pointerType,
    button: 0,
    bubbles: true,
  });
  Object.defineProperties(event, {
    clientX: { configurable: true, get: () => clientX },
    clientY: { configurable: true, get: () => 120 },
  });
  fireEvent(svg, event);
}

function scrubChart(svg: Element, clientX: number, pointerType: "mouse" | "touch" = "mouse") {
  firePointer(svg, "pointerDown", clientX, pointerType);
  firePointer(svg, "pointerMove", clientX, pointerType);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("nearestObservedPoint", () => {
  it("returns the nearest real observation, never an interpolated price", () => {
    const plotted = [
      { date: "2026-09-01", price: 60_000, platform: "best", x: 72, y: 100 },
      { date: "2026-09-10", price: 55_000, platform: "best", x: 372, y: 140 },
      { date: "2026-09-18", price: 58_000, platform: "best", x: 672, y: 120 },
    ];
    const hit = nearestObservedPoint(plotted, 250, 0, 720);
    expect(hit?.date).toBe("2026-09-10");
    expect(hit?.price).toBe(55_000);
  });

  it("picks a real point when multiple retailers share a date", () => {
    const plotted = [
      { date: "2026-09-10", price: 55_000, platform: "amazon", x: 200, y: 140 },
      { date: "2026-09-10", price: 56_500, platform: "flipkart", x: 200, y: 120 },
      { date: "2026-09-18", price: 58_000, platform: "best", x: 672, y: 120 },
    ];
    const hit = nearestObservedPoint(plotted, 210, 0, 720);
    expect(hit?.date).toBe("2026-09-10");
    expect(["amazon", "flipkart"]).toContain(hit?.platform);
  });

  it("handles a one-point series", () => {
    const plotted = [{ date: "2026-09-10", price: 55_000, platform: "best", x: 360, y: 140 }];
    const hit = nearestObservedPoint(plotted, 10, 0, 720);
    expect(hit?.price).toBe(55_000);
  });
});

describe("observationsAtDate / priceChangeFromPrevious", () => {
  it("collects peer retailers on the same calendar day only", () => {
    const plotted = [
      { date: "2026-09-10T15:20:00Z", price: 55_000, platform: "flipkart", x: 200, y: 140 },
      { date: "2026-09-10T18:00:00Z", price: 56_500, platform: "reliancedigital", x: 200, y: 120 },
      { date: "2026-09-18T09:00:00Z", price: 58_000, platform: "flipkart", x: 672, y: 120 },
    ];
    const peers = observationsAtDate(plotted, "2026-09-10T15:20:00Z");
    expect(peers).toHaveLength(2);
    expect(peers.map((p) => p.platform).sort()).toEqual(["flipkart", "reliancedigital"]);
  });

  it("reports change from the previous real observation when available", () => {
    const series = [
      { date: "2026-09-01", price: 60_000, platform: "flipkart", x: 72, y: 100 },
      { date: "2026-09-10", price: 55_000, platform: "flipkart", x: 372, y: 140 },
    ];
    const change = priceChangeFromPrevious(series, series[1]!);
    expect(change?.amount).toBe(-5_000);
    expect(change?.percent).toBeCloseTo(-8.333, 2);
  });

  it("returns null when no prior observation exists", () => {
    const series = [{ date: "2026-09-10", price: 55_000, platform: "flipkart", x: 372, y: 140 }];
    expect(priceChangeFromPrevious(series, series[0]!)).toBeNull();
  });
});

describe("segmentByObservationGaps", () => {
  it("breaks the line across long unobserved intervals without drawing a bridge", () => {
    const points = [
      { date: "2026-09-01", price: 50_000, platform: "best", x: 0, y: 0 },
      { date: "2026-09-14", price: 45_000, platform: "best", x: 100, y: 10 },
    ];
    expect(observationGapDays(points[0]!.date, points[1]!.date)).toBeGreaterThan(7);
    const segments = segmentByObservationGaps(points);
    expect(segments).toHaveLength(0);
  });

  it("keeps nearby observations on a solid segment", () => {
    const points = [
      { date: "2026-09-01", price: 50_000, platform: "best", x: 0, y: 0 },
      { date: "2026-09-03", price: 49_000, platform: "best", x: 40, y: 5 },
      { date: "2026-09-05", price: 48_000, platform: "best", x: 80, y: 10 },
    ];
    const segments = segmentByObservationGaps(points);
    expect(segments).toHaveLength(1);
    expect(segments[0]?.gapped).toBe(false);
    expect(segments[0]?.points).toHaveLength(3);
  });

  it("splits dense clusters separated by a long gap into separate solid segments", () => {
    const points = [
      { date: "2026-09-01", price: 50_000, platform: "best", x: 0, y: 0 },
      { date: "2026-09-02", price: 49_500, platform: "best", x: 20, y: 2 },
      { date: "2026-09-20", price: 45_000, platform: "best", x: 100, y: 10 },
      { date: "2026-09-21", price: 44_500, platform: "best", x: 120, y: 12 },
    ];
    const segments = segmentByObservationGaps(points);
    expect(segments).toHaveLength(2);
    expect(segments.every((segment) => !segment.gapped)).toBe(true);
    expect(segments[0]?.points).toHaveLength(2);
    expect(segments[1]?.points).toHaveLength(2);
  });
});

describe("PriceHistoryChart", () => {
  it("renders an accessible summary without a heavyweight chart runtime", () => {
    render(
      <PriceHistoryChart
        history={[
          point("2026-09-01", 60_000),
          point("2026-09-10", 55_000),
          point("2026-09-20", 58_000),
        ]}
      />,
    );

    expect(screen.getByRole("img")).toHaveAccessibleName(/₹55,000.*₹60,000.*3 observations/i);
    expect(screen.getByRole("img")).toHaveAccessibleName(/long gaps with no observations are left blank/i);
  });

  it("documents blank gap semantics in the accessible summary for sparse history", () => {
    render(
      <PriceHistoryChart
        history={[point("2026-09-01", 50_000), point("2026-09-20", 45_000)]}
      />,
    );
    expect(screen.getByRole("img")).toHaveAccessibleName(/long gaps with no observations are left blank/i);
  });

  it("shows the limited-data state when fewer than two valid points exist", () => {
    render(<PriceHistoryChart history={[point("2026-09-01", 60_000), point("", null)]} />);
    expect(screen.getByText("Not enough price history yet")).toBeInTheDocument();
    expect(
      screen.getByText(/still collecting price history for this configuration/i),
    ).toBeInTheDocument();
  });

  it("exposes a textual history table alongside the chart", () => {
    render(
      <PriceHistoryChart
        history={[
          point("2026-07-01", 60_000),
          point("2026-07-10", 55_000),
          point("2026-07-20", 58_000),
        ]}
      />,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Observed best price")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
  });

  it("lets the user change the time window and only lists series with data", async () => {
    const user = userEvent.setup();
    render(
      <PriceHistoryChart
        history={[
          { date: "2026-09-01", best_price: 60_000, platform_prices: { amazon: 60_000 } },
          { date: "2026-09-10", best_price: 55_000, platform_prices: { amazon: 55_000 } },
          { date: "2026-09-18", best_price: 58_000, platform_prices: { amazon: 58_000 } },
        ]}
        payload={{
          product_id: "p1",
          window: "all",
          days: 3650,
          best_price: [
            { date: "2026-09-01", price: 60_000, observed: true },
            { date: "2026-09-10", price: 55_000, observed: true },
            { date: "2026-09-18", price: 58_000, observed: true },
          ],
          platforms: {
            amazon: [
              { date: "2026-09-01", price: 60_000, observed: true },
              { date: "2026-09-18", price: 58_000, observed: true },
            ],
          },
          missing_days_are_unobserved: true,
          history: [],
        }}
      />,
    );
    expect(screen.getByRole("button", { name: "30D" })).toHaveAttribute("aria-pressed", "false");
    await user.click(screen.getByRole("button", { name: "30D" }));
    expect(screen.getByRole("button", { name: "30D" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Best" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /amazon/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /flipkart/i })).not.toBeInTheDocument();
  });

  it("shows crosshair and multi-retailer tooltip after pointer scrub", () => {
    mockSvgLayout();
    const { container } = render(
      <PriceHistoryChart history={multiPayload.history} payload={multiPayload} />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
    scrubChart(svg!, 360, "mouse");
    expect(screen.getByTestId("price-history-crosshair")).toBeInTheDocument();
    expect(screen.getByTestId("price-history-tooltip")).toBeInTheDocument();
  });

  it("supports touch scrub and keeps selected observation after release", () => {
    mockSvgLayout();
    const { container } = render(
      <PriceHistoryChart history={multiPayload.history} payload={multiPayload} />,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
    scrubChart(svg!, 200, "touch");
    firePointer(svg!, "pointerMove", 400, "touch");
    expect(screen.getByTestId("price-history-tooltip")).toBeInTheDocument();
    firePointer(svg!, "pointerUp", 400, "touch");
    firePointer(svg!, "pointerLeave", 400, "touch");
    expect(screen.getByTestId("price-history-tooltip")).toBeInTheDocument();
  });

  it("respects retailer toggles so disabled series leave the legend pressed-off", async () => {
    const user = userEvent.setup();
    render(<PriceHistoryChart history={multiPayload.history} payload={multiPayload} />);
    const flipkart = screen.getByRole("button", { name: /flipkart/i });
    expect(flipkart).toHaveAttribute("aria-pressed", "true");
    await user.click(flipkart);
    expect(flipkart).toHaveAttribute("aria-pressed", "false");
  });

  it("clears interaction state when the range changes", async () => {
    mockSvgLayout();
    const user = userEvent.setup();
    const { container } = render(
      <PriceHistoryChart history={multiPayload.history} payload={multiPayload} />,
    );
    const svg = container.querySelector("svg");
    scrubChart(svg!, 360, "mouse");
    expect(screen.getByTestId("price-history-tooltip")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "1Y" }));
    expect(screen.queryByTestId("price-history-tooltip")).not.toBeInTheDocument();
  });

  it("keeps range and series controls keyboard usable", async () => {
    const user = userEvent.setup();
    render(<PriceHistoryChart history={multiPayload.history} payload={multiPayload} />);
    await user.tab();
    expect(screen.getByRole("button", { name: "30D" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: "30D" })).toHaveAttribute("aria-pressed", "true");
  });
});

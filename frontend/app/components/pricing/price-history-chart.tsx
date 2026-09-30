import { useMemo, useRef, useState } from "react";
import { formatPrice, validPrice } from "~/lib/formatting/price";
import { priceStatistics } from "~/lib/pricing/statistics";
import { platformDisplayName } from "~/lib/search/platforms";
import type { PriceHistory, PricePoint } from "~/lib/api/schemas";
import { cn } from "~/components/ui/cn";

const WIDTH = 720;
const HEIGHT = 280;
const PADDING = { top: 16, right: 18, bottom: 44, left: 72 } as const;
const PLOT_WIDTH = WIDTH - PADDING.left - PADDING.right;
const PLOT_HEIGHT = HEIGHT - PADDING.top - PADDING.bottom;
const GAP_DAYS = 7;
const Y_TICKS = 4;

const WINDOWS = [
  { id: "30d", label: "30D", days: 30 },
  { id: "90d", label: "90D", days: 90 },
  { id: "180d", label: "6M", days: 180 },
  { id: "1y", label: "1Y", days: 365 },
  { id: "all", label: "All", days: 3650 },
] as const;

const SERIES_COLORS: Record<string, string> = {
  best: "#0f766e",
  amazon: "#c2410c",
  flipkart: "#1d4ed8",
  croma: "#1e3a8a",
  reliancedigital: "#b91c1c",
  vijaysales: "#6d28d9",
  poorvika: "#0f766e",
};

interface ChartPoint {
  date: string;
  price: number;
  platform: string;
}

interface PlottedPoint extends ChartPoint {
  x: number;
  y: number;
}

/** Day gap between two ISO observation dates. */
export function observationGapDays(a: string, b: string): number {
  const left = Date.parse(a);
  const right = Date.parse(b);
  if (Number.isNaN(left) || Number.isNaN(right)) return 0;
  return Math.abs(right - left) / 86_400_000;
}

/**
 * Split a plotted series into solid segments only.
 * Gaps longer than maxGapDays break the line entirely (no dashed bridge),
 * so unobserved intervals are not implied as continuous price trajectories.
 * Observation markers remain for every real point.
 */
export function segmentByObservationGaps(
  points: PlottedPoint[],
  maxGapDays = GAP_DAYS,
): Array<{ points: PlottedPoint[]; gapped: boolean }> {
  if (points.length === 0) return [];
  const segments: Array<{ points: PlottedPoint[]; gapped: boolean }> = [];
  let current: PlottedPoint[] = [points[0]!];
  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1]!;
    const next = points[i]!;
    if (observationGapDays(prev.date, next.date) > maxGapDays) {
      if (current.length >= 2) segments.push({ points: current, gapped: false });
      current = [next];
    } else {
      current.push(next);
    }
  }
  if (current.length >= 2) segments.push({ points: current, gapped: false });
  return segments;
}

function pointDate(point: PricePoint): string {
  return point.date ?? point.observed_at ?? "";
}

function compactPrice(value: number): string {
  if (value >= 100_000) return `₹${(value / 100_000).toFixed(value >= 1_000_000 ? 0 : 1)}L`;
  if (value >= 1_000) return `₹${Math.round(value / 1_000)}k`;
  return `₹${Math.round(value)}`;
}

function shortDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
  }).format(date);
}

function fullDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function fullDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

/** Same calendar-day (UTC date prefix) observations across visible series. */
export function observationsAtDate(
  plotted: PlottedPoint[],
  date: string,
): PlottedPoint[] {
  const day = date.slice(0, 10);
  return plotted.filter((point) => point.date.slice(0, 10) === day);
}

/** Change vs previous observation in the same series (null if unavailable). */
export function priceChangeFromPrevious(
  series: PlottedPoint[],
  point: PlottedPoint,
): { amount: number; percent: number } | null {
  const ordered = [...series].sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  const index = ordered.findIndex(
    (row) => row.date === point.date && row.price === point.price && row.platform === point.platform,
  );
  if (index <= 0) return null;
  const prev = ordered[index - 1]!;
  const amount = point.price - prev.price;
  if (!Number.isFinite(amount) || prev.price <= 0) return null;
  return { amount, percent: (amount / prev.price) * 100 };
}

function withinDays(dateValue: string, days: number): boolean {
  const parsed = Date.parse(dateValue);
  if (Number.isNaN(parsed)) return true;
  const cutoff = Date.now() - days * 86_400_000;
  return parsed >= cutoff;
}

function seriesLabel(id: string): string {
  return id === "best" ? "Best" : platformDisplayName(id) || id;
}

function collectSeries(history: PricePoint[], payload?: PriceHistory | null): Record<string, ChartPoint[]> {
  const series: Record<string, ChartPoint[]> = { best: [] };
  if (payload?.best_price?.length) {
    series.best = payload.best_price
      .filter((point) => validPrice(point.price))
      .map((point) => ({ date: point.date, price: point.price, platform: "best" }));
  } else {
    for (const point of history) {
      const date = pointDate(point);
      if (date && validPrice(point.best_price)) {
        series.best?.push({ date, price: point.best_price, platform: "best" });
      }
    }
  }
  const platformMap = payload?.platforms ?? {};
  if (Object.keys(platformMap).length > 0) {
    for (const [platform, points] of Object.entries(platformMap)) {
      series[platform] = (points || [])
        .filter((point) => validPrice(point.price))
        .map((point) => ({ date: point.date, price: point.price, platform }));
    }
    return series;
  }
  for (const point of history) {
    const date = pointDate(point);
    const extras = point as PricePoint & Record<string, unknown>;
    const nested = extras.platform_prices;
    if (nested && typeof nested === "object") {
      for (const [platform, raw] of Object.entries(nested as Record<string, unknown>)) {
        if (date && validPrice(raw)) {
          series[platform] ??= [];
          series[platform].push({ date, price: Number(raw), platform });
        }
      }
    }
    for (const key of ["amazon_price", "flipkart_price", "croma_price", "reliancedigital_price"] as const) {
      const price = extras[key];
      if (date && validPrice(price)) {
        const platform = key.replace("_price", "");
        series[platform] ??= [];
        series[platform].push({ date, price: Number(price), platform });
      }
    }
  }
  return series;
}

/** Pointer X may interpolate; returned point is always a real observation. */
export function nearestObservedPoint(
  plotted: PlottedPoint[],
  clientX: number,
  svgLeft: number,
  svgWidth: number,
): PlottedPoint | null {
  if (plotted.length === 0 || svgWidth <= 0) return null;
  const ratio = Math.min(1, Math.max(0, (clientX - svgLeft) / svgWidth));
  const targetX = PADDING.left + ratio * PLOT_WIDTH;
  let best: PlottedPoint | null = null;
  let bestDist = Number.POSITIVE_INFINITY;
  for (const point of plotted) {
    const dist = Math.abs(point.x - targetX);
    if (dist < bestDist) {
      bestDist = dist;
      best = point;
    }
  }
  return best;
}

function EmptyHistory({ only }: { only?: ChartPoint | null }) {
  return (
    <div className="rounded-md bg-surface-muted p-6 text-center">
      <h3 className="font-semibold text-ink">Not enough price history yet</h3>
      <p className="mt-2 text-sm text-ink-muted">
        Mayabu is still collecting price history for this configuration.
      </p>
      {only ? (
        <p className="mt-4 text-sm text-ink">
          Latest observed best price: {formatPrice(only.price)} on {fullDate(only.date)}
        </p>
      ) : null}
    </div>
  );
}

export function PriceHistoryChart({
  history,
  payload,
}: {
  history: PricePoint[];
  payload?: PriceHistory | null;
}) {
  const allSeries = useMemo(() => collectSeries(history, payload), [history, payload]);
  const available = Object.entries(allSeries)
    .filter(([, points]) => points.length > 0)
    .map(([id]) => id);
  const [windowId, setWindowId] = useState<(typeof WINDOWS)[number]["id"]>("90d");
  const days = WINDOWS.find((item) => item.id === windowId)?.days ?? 90;
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [hoverPoint, setHoverPoint] = useState<PlottedPoint | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<PlottedPoint | null>(null);
  const [scrubbing, setScrubbing] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const plotRef = useRef<HTMLDivElement>(null);

  const visibleIds = available.filter((id) => !hidden[id]);
  const selected =
    visibleIds.length > 0
      ? visibleIds
      : available.includes("best")
        ? ["best"]
        : available.slice(0, 1);

  const filtered: Record<string, ChartPoint[]> = {};
  for (const id of selected) {
    filtered[id] = (allSeries[id] || []).filter(
      (point) => windowId === "all" || withinDays(point.date, days),
    );
  }
  const data = filtered.best?.length ? filtered.best : Object.values(filtered)[0] || [];

  if (
    (allSeries.best?.length || 0) < 2 &&
    available.filter((id) => id !== "best").every((id) => (allSeries[id]?.length || 0) < 2)
  ) {
    return <EmptyHistory only={allSeries.best?.[0] ?? null} />;
  }

  const plotPoints = selected.flatMap((id) => filtered[id] || []);
  const statistics = priceStatistics(plotPoints.map((point) => point.price));

  const rangeControls = (
    <div className="mb-4 flex flex-wrap items-center gap-2" role="group" aria-label="History range">
      {WINDOWS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={cn(
            "min-h-9 rounded-md border px-3 text-xs font-semibold",
            windowId === item.id
              ? "border-accent bg-accent text-white"
              : "border-line bg-white text-ink-muted hover:border-accent",
          )}
          aria-pressed={windowId === item.id}
          onClick={() => {
            setWindowId(item.id);
            setSelectedPoint(null);
            setHoverPoint(null);
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  );

  if (!statistics || (data.length < 2 && plotPoints.length < 2)) {
    return (
      <div>
        {rangeControls}
        <EmptyHistory />
        <p className="mt-2 text-center text-xs text-ink-muted">
          Try a wider range — this window has fewer than two observations.
        </p>
      </div>
    );
  }

  const rawRange = statistics.maximum - statistics.minimum;
  const margin = rawRange > 0 ? rawRange * 0.08 : Math.max(statistics.maximum * 0.02, 1);
  const yMinimum = Math.max(0, statistics.minimum - margin);
  const yMaximum = statistics.maximum + margin;
  const yRange = Math.max(1, yMaximum - yMinimum);

  function coordinates(points: ChartPoint[]): PlottedPoint[] {
    if (points.length === 0) return [];
    // Space by observation index — gaps remain visible as longer segments between real points.
    const xStep = PLOT_WIDTH / Math.max(1, points.length - 1);
    return points.map((point, index) => ({
      ...point,
      x: PADDING.left + index * xStep,
      y: PADDING.top + ((yMaximum - point.price) / yRange) * PLOT_HEIGHT,
    }));
  }

  const plottedBySeries: Record<string, PlottedPoint[]> = {};
  for (const id of selected) {
    plottedBySeries[id] = coordinates(filtered[id] || []);
  }
  const allPlotted = selected.flatMap((id) => plottedBySeries[id] || []);

  const current = data[data.length - 1] ?? plotPoints[plotPoints.length - 1];
  if (!current) return <EmptyHistory />;

  const active = hoverPoint ?? selectedPoint;
  const activePeers = active ? observationsAtDate(allPlotted, active.date) : [];
  const tooltipRows = activePeers.length > 0 ? activePeers : active ? [active] : [];
  const tooltipFlipLeft = active ? active.x / WIDTH > 0.62 : false;
  const windowLabel =
    WINDOWS.find((item) => item.id === windowId)?.label.replace("D", "-day").replace("M", "-month") ??
    "tracked";
  const lowLabel =
    windowId === "all" ? "Tracked low" : windowId === "90d" ? "90-day low" : `${windowLabel} low`;

  const summary = `Current ${formatPrice(current.price)}. ${lowLabel} ${formatPrice(statistics.minimum)}. Tracked high ${formatPrice(statistics.maximum)}. ${statistics.count} observations. Lines connect nearby observations only; long gaps with no observations are left blank (not interpolated).`;
  const textSummary = summary;
  const tableRows = (filtered.best?.length ? filtered.best : data).slice(-12);
  const overlayBusy = selected.length > 4;

  function resolvePointer(clientX: number): PlottedPoint | null {
    const svg = svgRef.current;
    if (!svg) return null;
    const rect = svg.getBoundingClientRect();
    const width = rect.width > 0 ? rect.width : WIDTH;
    const left = rect.width > 0 ? rect.left : 0;
    return nearestObservedPoint(allPlotted, clientX, left, width);
  }

  function onPointerMove(clientX: number) {
    const next = resolvePointer(clientX);
    setHoverPoint(next);
  }

  function onPointerSelect(clientX: number) {
    const next = resolvePointer(clientX);
    setSelectedPoint(next);
    setHoverPoint(next);
  }

  function beginScrub(clientX: number, pointerId: number, target: Element) {
    setScrubbing(true);
    onPointerSelect(clientX);
    if ("setPointerCapture" in target) {
      try {
        (target as HTMLElement).setPointerCapture(pointerId);
      } catch {
        /* ignore */
      }
    }
  }

  function endScrub() {
    setScrubbing(false);
  }

  return (
    <div>
      {rangeControls}
      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Price series">
        {available.map((id) => {
          const activeSeries = selected.includes(id);
          return (
            <button
              key={id}
              type="button"
              className={cn(
                "inline-flex min-h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold",
                activeSeries ? "border-line bg-white text-ink" : "border-line bg-slate-50 text-ink-muted",
              )}
              aria-pressed={activeSeries}
              onClick={() => {
                setHidden((currentHidden) => ({ ...currentHidden, [id]: !currentHidden[id] }));
                setSelectedPoint(null);
                setHoverPoint(null);
              }}
            >
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: SERIES_COLORS[id] || "#334155" }}
                aria-hidden="true"
              />
              {seriesLabel(id)}
            </button>
          );
        })}
      </div>
      {overlayBusy ? (
        <p className="mb-3 text-xs text-ink-muted">
          Many stores are selected. Hide series in the legend if the chart becomes hard to read.
        </p>
      ) : null}
      <p className="mb-4 text-sm text-ink-muted">{textSummary}</p>

      <div className="relative" ref={plotRef}>
        <div
          className="w-full overflow-hidden motion-safe:transition-opacity"
          role="img"
          aria-label={summary}
        >
          <svg
            ref={svgRef}
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className={cn("h-auto w-full", scrubbing ? "touch-none" : "touch-pan-y")}
            aria-hidden="true"
            focusable="false"
            onPointerDown={(event) => {
              if (event.pointerType === "mouse" && event.button !== 0) return;
              const clientX = Number(event.clientX ?? event.nativeEvent?.clientX);
              if (!Number.isFinite(clientX)) return;
              beginScrub(clientX, event.pointerId, event.currentTarget);
            }}
            onPointerMove={(event) => {
              if (event.pointerType === "mouse" || scrubbing) {
                const clientX = Number(event.clientX ?? event.nativeEvent?.clientX);
                if (!Number.isFinite(clientX)) return;
                onPointerMove(clientX);
              }
            }}
            onPointerUp={endScrub}
            onPointerCancel={endScrub}
            onPointerLeave={() => {
              if (!scrubbing) setHoverPoint(null);
            }}
          >
            {Array.from({ length: Y_TICKS + 1 }, (_, index) => {
              const ratio = index / Y_TICKS;
              const y = PADDING.top + ratio * PLOT_HEIGHT;
              const value = yMaximum - ratio * yRange;
              return (
                <g key={index}>
                  <line
                    x1={PADDING.left}
                    x2={WIDTH - PADDING.right}
                    y1={y}
                    y2={y}
                    className="stroke-slate-200"
                    strokeDasharray="4 4"
                  />
                  <text
                    x={PADDING.left - 10}
                    y={y + 4}
                    textAnchor="end"
                    className="fill-slate-500 text-[11px]"
                  >
                    {compactPrice(value)}
                  </text>
                </g>
              );
            })}

            {selected.map((id) => {
              const coords = plottedBySeries[id] || [];
              if (coords.length === 0) return null;
              const segments = segmentByObservationGaps(coords);
              return (
                <g key={id}>
                  {segments.map((segment, segmentIndex) => {
                    if (segment.points.length < 2) return null;
                    const polyline = segment.points.map((point) => `${point.x},${point.y}`).join(" ");
                    return (
                      <polyline
                        key={`${id}-seg-${segmentIndex}`}
                        points={polyline}
                        fill="none"
                        stroke={SERIES_COLORS[id] || "#334155"}
                        strokeWidth={id === "best" ? 3 : 2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        opacity={0.92}
                        vectorEffect="non-scaling-stroke"
                      />
                    );
                  })}
                  {coords.map((point, index) => {
                    const isActive =
                      active &&
                      active.date.slice(0, 10) === point.date.slice(0, 10) &&
                      active.platform === point.platform;
                    return (
                      <g key={`${id}-${point.date}-${index}`}>
                        <circle
                          cx={point.x}
                          cy={point.y}
                          r={14}
                          fill="transparent"
                          className="pointer-events-auto"
                        />
                        <circle
                          cx={point.x}
                          cy={point.y}
                          r={isActive ? 5.5 : coords.length <= 48 ? 3.5 : 2.5}
                          fill={SERIES_COLORS[id] || "#334155"}
                          stroke={isActive ? "#fff" : "transparent"}
                          strokeWidth={2}
                          className="pointer-events-none"
                        />
                      </g>
                    );
                  })}
                </g>
              );
            })}

            {/* Interaction crosshair — snaps to nearest real observation */}
            {active ? (
              <g data-testid="price-history-crosshair">
                <line
                  x1={active.x}
                  x2={active.x}
                  y1={PADDING.top}
                  y2={PADDING.top + PLOT_HEIGHT}
                  stroke="#64748b"
                  strokeWidth="1"
                  strokeOpacity="0.55"
                  vectorEffect="non-scaling-stroke"
                />
                {tooltipRows.map((row) => (
                  <circle
                    key={`xh-${row.platform}-${row.date}`}
                    cx={row.x}
                    cy={row.y}
                    r="6"
                    fill="none"
                    stroke={SERIES_COLORS[row.platform] || "#334155"}
                    strokeWidth="2"
                    opacity="0.9"
                  />
                ))}
              </g>
            ) : null}

            {/* Current marker on primary series */}
            {(() => {
              const primary = plottedBySeries.best?.length
                ? plottedBySeries.best
                : plottedBySeries[selected[0] || ""] || [];
              const last = primary[primary.length - 1];
              if (!last) return null;
              return (
                <g>
                  <circle
                    cx={last.x}
                    cy={last.y}
                    r="6"
                    fill="none"
                    stroke="#0f766e"
                    strokeWidth="2"
                    opacity="0.55"
                  />
                  <circle cx={last.x} cy={last.y} r="3.5" fill="#0f766e" />
                </g>
              );
            })()}

            {/* Tracked low marker */}
            {(() => {
              const lowPoint = allPlotted.reduce<PlottedPoint | null>((best, point) => {
                if (!best || point.price < best.price) return point;
                return best;
              }, null);
              if (!lowPoint) return null;
              return (
                <g>
                  <line
                    x1={lowPoint.x}
                    x2={lowPoint.x}
                    y1={PADDING.top}
                    y2={PADDING.top + PLOT_HEIGHT}
                    stroke="#94a3b8"
                    strokeDasharray="3 4"
                    strokeWidth="1"
                  />
                </g>
              );
            })()}

            {(() => {
              const primary = coordinates(data);
              const labelIndexes = Array.from(
                new Set([0, Math.floor((primary.length - 1) / 2), primary.length - 1]),
              );
              return labelIndexes.map((index) => {
                const point = primary[index];
                if (!point) return null;
                const anchor =
                  index === 0 ? "start" : index === primary.length - 1 ? "end" : "middle";
                return (
                  <text
                    key={`${point.date}-${index}-label`}
                    x={point.x}
                    y={HEIGHT - 14}
                    textAnchor={anchor}
                    className="fill-slate-500 text-[11px]"
                  >
                    {shortDate(point.date)}
                  </text>
                );
              });
            })()}
          </svg>
        </div>

        {/* Floating tooltip (desktop hover + touch scrub) */}
        {active && tooltipRows.length > 0 ? (
          <div
            className="pointer-events-none absolute z-10 max-w-[14rem] rounded-md border border-line bg-white px-3 py-2 text-sm shadow-soft"
            style={{
              left: tooltipFlipLeft
                ? `clamp(0.5rem, ${(active.x / WIDTH) * 100}% - 13.5rem, calc(100% - 14.5rem))`
                : `clamp(0.5rem, ${(active.x / WIDTH) * 100}% + 0.75rem, calc(100% - 14.5rem))`,
              top: `clamp(0.5rem, ${(active.y / HEIGHT) * 100}% - 1rem, calc(100% - 8rem))`,
            }}
            role="status"
            data-testid="price-history-tooltip"
          >
            <p className="text-xs font-medium text-ink-muted">{fullDateTime(active.date)}</p>
            <ul className="mt-1.5 space-y-1">
              {tooltipRows.map((row) => {
                const change = priceChangeFromPrevious(plottedBySeries[row.platform] || [], row);
                return (
                  <li key={`${row.platform}-${row.date}`} className="flex items-baseline justify-between gap-3">
                    <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink">
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ background: SERIES_COLORS[row.platform] || "#334155" }}
                        aria-hidden="true"
                      />
                      {seriesLabel(row.platform)}
                    </span>
                    <span className="text-right">
                      <span className="price-numerals text-sm font-semibold text-ink">
                        {formatPrice(row.price)}
                      </span>
                      {change && Math.abs(change.amount) >= 1 ? (
                        <span
                          className={cn(
                            "ml-1.5 text-[10px] font-medium",
                            change.amount < 0 ? "text-emerald-700" : "text-ink-muted",
                          )}
                        >
                          {change.amount < 0 ? "↓" : "↑"}{" "}
                          {formatPrice(Math.abs(change.amount))}
                        </span>
                      ) : null}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
      </div>

      {/* Sticky detail / dismiss for touch */}
      {selectedPoint ? (
        <div className="mt-3 flex justify-end sm:hidden">
          <button
            type="button"
            className="text-xs font-semibold text-accent hover:underline"
            onClick={() => {
              setSelectedPoint(null);
              setHoverPoint(null);
            }}
          >
            Clear selection
          </button>
        </div>
      ) : (
        <p className="mt-3 text-xs text-ink-soft sm:hidden">
          Drag across the chart to inspect exact observations.
        </p>
      )}

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-ink-soft">Current</dt>
          <dd className="price-numerals font-semibold text-ink">{formatPrice(current.price)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">{lowLabel}</dt>
          <dd className="price-numerals font-semibold text-ink">{formatPrice(statistics.minimum)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Tracked high</dt>
          <dd className="price-numerals font-semibold text-ink">{formatPrice(statistics.maximum)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Observations</dt>
          <dd className="font-semibold text-ink">{statistics.count}</dd>
        </div>
      </dl>

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[16rem] text-left text-sm">
          <caption className="sr-only">Recent observed prices</caption>
          <thead>
            <tr className="border-b border-line text-ink-soft">
              <th scope="col" className="py-2 font-medium">
                Date
              </th>
              <th scope="col" className="py-2 font-medium">
                Observed best price
              </th>
            </tr>
          </thead>
          <tbody>
            {[...tableRows].reverse().map((point) => (
              <tr key={point.date} className="border-b border-line/70">
                <td className="py-2 text-ink-muted">{fullDate(point.date)}</td>
                <td className="price-numerals py-2 font-semibold text-ink">
                  {formatPrice(point.price)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

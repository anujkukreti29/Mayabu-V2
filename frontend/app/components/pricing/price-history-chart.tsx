import { formatPrice, validPrice } from "~/lib/formatting/price";
import { priceStatistics } from "~/lib/pricing/statistics";
import type { PricePoint } from "~/lib/api/schemas";

const WIDTH = 720;
const HEIGHT = 280;
const PADDING = { top: 16, right: 18, bottom: 44, left: 72 } as const;
const PLOT_WIDTH = WIDTH - PADDING.left - PADDING.right;
const PLOT_HEIGHT = HEIGHT - PADDING.top - PADDING.bottom;
const Y_TICKS = 4;

interface ChartPoint {
  date: string;
  price: number;
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

function priceValues(points: ChartPoint[]): Iterable<number> {
  return {
    *[Symbol.iterator]() {
      for (const point of points) yield point.price;
    },
  };
}

export function PriceHistoryChart({ history }: { history: PricePoint[] }) {
  const data: ChartPoint[] = [];
  for (const point of history) {
    const date = pointDate(point);
    if (date && validPrice(point.best_price)) {
      data.push({ date, price: point.best_price });
    }
  }

  if (data.length < 2) {
    return (
      <div className="rounded-xl bg-slate-50 p-6 text-center">
        <h3 className="font-black">More price history is needed</h3>
        <p className="mt-2 text-sm text-slate-600">
          Mayabu does not yet have enough observations to show a reliable trend for this product.
        </p>
      </div>
    );
  }

  const statistics = priceStatistics(priceValues(data));
  if (!statistics) return null;

  const rawRange = statistics.maximum - statistics.minimum;
  const margin = rawRange > 0 ? rawRange * 0.08 : Math.max(statistics.maximum * 0.02, 1);
  const yMinimum = Math.max(0, statistics.minimum - margin);
  const yMaximum = statistics.maximum + margin;
  const yRange = Math.max(1, yMaximum - yMinimum);
  const xStep = PLOT_WIDTH / Math.max(1, data.length - 1);

  const coordinates = data.map((point, index) => ({
    ...point,
    x: PADDING.left + index * xStep,
    y: PADDING.top + ((yMaximum - point.price) / yRange) * PLOT_HEIGHT,
  }));
  const polyline = coordinates.map((point) => `${point.x},${point.y}`).join(" ");
  const labelIndexes = Array.from(new Set([0, Math.floor((data.length - 1) / 2), data.length - 1]));
  const summary = `Recorded price ranged from ${formatPrice(statistics.minimum)} to ${formatPrice(statistics.maximum)} across ${statistics.count} observations.`;

  return (
    <div>
      <p className="mb-4 text-sm text-slate-600">{summary}</p>
      <div className="w-full overflow-hidden" role="img" aria-label={summary}>
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="h-auto w-full text-brand-600"
          aria-hidden="true"
          focusable="false"
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

          <polyline
            points={polyline}
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />

          {coordinates.length <= 40
            ? coordinates.map((point, index) => (
                <circle
                  key={`${point.date}-${index}`}
                  cx={point.x}
                  cy={point.y}
                  r="3"
                  fill="currentColor"
                >
                  <title>{`${shortDate(point.date)}: ${formatPrice(point.price)}`}</title>
                </circle>
              ))
            : null}

          {labelIndexes.map((index) => {
            const point = coordinates[index];
            if (!point) return null;
            const anchor = index === 0 ? "start" : index === data.length - 1 ? "end" : "middle";
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
          })}
        </svg>
      </div>
    </div>
  );
}

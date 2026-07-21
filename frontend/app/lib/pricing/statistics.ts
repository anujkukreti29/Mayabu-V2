import { validPrice } from "~/lib/formatting/price";

export interface PriceStatistics {
  count: number;
  minimum: number;
  maximum: number;
  average: number;
}

/** Calculate price statistics in one pass with constant additional space. */
export function priceStatistics(values: Iterable<unknown>): PriceStatistics | null {
  let count = 0;
  let minimum = Number.POSITIVE_INFINITY;
  let maximum = Number.NEGATIVE_INFINITY;
  let total = 0;

  for (const value of values) {
    if (!validPrice(value)) continue;
    count += 1;
    total += value;
    if (value < minimum) minimum = value;
    if (value > maximum) maximum = value;
  }

  if (count === 0) return null;
  return { count, minimum, maximum, average: total / count };
}

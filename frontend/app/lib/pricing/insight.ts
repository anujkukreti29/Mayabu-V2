import { formatPrice, validPrice } from "~/lib/formatting/price";
import { priceStatistics } from "~/lib/pricing/statistics";

export interface BuyingInsight {
  badge: string;
  message: string;
}

const LIMITED_DATA: BuyingInsight = {
  badge: "Limited data",
  message:
    "Mayabu does not yet have enough valid history to judge this recorded price. Verify the store listing before buying.",
};

export function buildBuyingInsight(
  currentPrice: unknown,
  historicalPrices: Iterable<unknown>,
): BuyingInsight {
  if (!validPrice(currentPrice)) return LIMITED_DATA;
  const statistics = priceStatistics(historicalPrices);
  if (!statistics || statistics.count < 3) return LIMITED_DATA;

  if (currentPrice <= statistics.minimum * 1.03) {
    return {
      badge: "Near observed low",
      message: `The current recorded price is close to Mayabu's lowest observed price of ${formatPrice(statistics.minimum)}. Historical data does not guarantee the future price.`,
    };
  }
  if (currentPrice > statistics.average * 1.08) {
    return {
      badge: "Above recent average",
      message: `The current recorded price is above the observed average of ${formatPrice(statistics.average)}. You may want to compare offers or verify before buying.`,
    };
  }
  return {
    badge: "Typical recorded range",
    message: `The current recorded price is near the average of Mayabu's available observations. Verify the final seller amount before purchase.`,
  };
}

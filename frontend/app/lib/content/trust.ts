export const supportedPlatforms = [
  "Amazon India",
  "Flipkart",
  "Croma",
  "Reliance Digital",
] as const;

export const supportedPlatformsText = supportedPlatforms
  .join(", ")
  .replace(", Reliance Digital", ", and Reliance Digital");

export const sellerStatement =
  "Mayabu is a product-discovery and price-intelligence service. Mayabu is not the seller.";

export const priceDisclaimer =
  "Prices, stock, delivery eligibility, coupons, and availability may change on seller websites. Always verify the final amount before purchase.";

export const trademarkStatement =
  "Mayabu is not affiliated with or endorsed by the listed marketplaces unless explicitly stated. Marketplace names and trademarks belong to their respective owners.";

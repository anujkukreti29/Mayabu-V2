/** Canonical retailer display names for search/product cards. */

const PLATFORM_DISPLAY: Record<string, string> = {
  amazon: "Amazon",
  "amazon india": "Amazon",
  flipkart: "Flipkart",
  croma: "Croma",
  reliancedigital: "Reliance Digital",
  "reliance digital": "Reliance Digital",
  vijaysales: "Vijay Sales",
  "vijay sales": "Vijay Sales",
  jiomart: "JioMart",
  poorvika: "Poorvika",
  bajajelectronics: "Bajaj Electronics",
  "bajaj electronics": "Bajaj Electronics",
};

export function platformDisplayName(platform: string | null | undefined): string {
  if (!platform) return "";
  const key = platform.trim().toLowerCase();
  return PLATFORM_DISPLAY[key] ?? platform;
}

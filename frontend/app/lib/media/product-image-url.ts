/** Safe product image URL normalization for browser rendering. */

const TRACKER_TOKENS = ["1x1", "pixel.gif", "tracking/pixel", "spacer.gif"];

export function normalizeProductImageUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  let text = value.trim();
  if (!text) return null;
  const lowerEmpty = text.toLowerCase();
  if (
    lowerEmpty === "null" ||
    lowerEmpty === "none" ||
    lowerEmpty === "undefined" ||
    lowerEmpty === "n/a"
  ) {
    return null;
  }
  if (text.startsWith("//")) {
    text = `https:${text}`;
  }
  const lower = text.toLowerCase();
  if (lower.startsWith("javascript:") || lower.startsWith("data:")) return null;
  if (!(lower.startsWith("https://") || lower.startsWith("http://"))) return null;
  if (TRACKER_TOKENS.some((token) => lower.includes(token))) return null;
  return text;
}

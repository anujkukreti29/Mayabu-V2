const APPROVED_RETAILERS = [
  "amazon.in",
  "www.amazon.in",
  "flipkart.com",
  "www.flipkart.com",
  "croma.com",
  "www.croma.com",
  "reliancedigital.in",
  "www.reliancedigital.in",
  "vijaysales.com",
  "www.vijaysales.com",
  "jiomart.com",
  "www.jiomart.com",
  "poorvika.com",
  "www.poorvika.com",
  "bajajelectronics.com",
  "www.bajajelectronics.com",
];

export function safeRetailerUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:") return null;
    if (!APPROVED_RETAILERS.includes(url.hostname.toLowerCase())) return null;
    return url.toString();
  } catch {
    return null;
  }
}

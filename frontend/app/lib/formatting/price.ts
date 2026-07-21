export function validPrice(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

export function formatPrice(value: unknown, fallback = "Price unavailable"): string {
  if (!validPrice(value)) return fallback;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
  }).format(value);
}

export function validDiscount(price: unknown, mrp: unknown, supplied?: unknown): number | null {
  if (!validPrice(price) || !validPrice(mrp) || mrp <= price) return null;
  const calculated = ((mrp - price) / mrp) * 100;
  const candidate =
    typeof supplied === "number" && Number.isFinite(supplied) ? supplied : calculated;
  if (candidate <= 0 || candidate >= 100) return null;
  return Math.round(candidate);
}

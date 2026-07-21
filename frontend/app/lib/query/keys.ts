export const searchKeys = {
  all: ["search"] as const,
  results: (params: Record<string, unknown>) => ["search", params] as const,
};
export const categoryKeys = {
  list: (category: string, params: Record<string, unknown>) =>
    ["category", category, params] as const,
};
export const productKeys = {
  detail: (productId: string) => ["product", productId] as const,
  offers: (productId: string) => ["product", productId, "offers"] as const,
  similarVariants: (productId: string) => ["product", productId, "similar-variants"] as const,
  priceHistory: (productId: string, range: number, platform?: string) =>
    ["product", productId, "price-history", range, platform ?? "all"] as const,
};
export const verificationKeys = {
  status: (productId: string) => ["verification", "status", productId] as const,
  job: (taskId: string) => ["verification", "job", taskId] as const,
};

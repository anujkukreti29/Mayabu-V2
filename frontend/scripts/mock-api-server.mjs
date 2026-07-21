import http from "node:http";

const port = Number(process.env.MOCK_API_PORT || 8001);
let jobReads = 0;

const product = {
  id: "p1",
  title: "ASUS Vivobook 15 X1504VA 16GB 512GB",
  brand: "ASUS",
  category: "laptop",
  specs: {
    family: "Vivobook 15",
    model_codes: ["X1504VA"],
    cpu_series: "Intel Core i5",
    cpu_models: ["Intel Core i5-1335U"],
    ram_gb: 16,
    storage_gb: 512,
    screen_inch: 15.6,
    generation: "13th Gen",
  },
  best_price: 54990,
  best_platform: "Amazon India",
  platform_count: 2,
  offer_count: 2,
  image_url: null,
  last_seen_at: "2026-07-18T12:00:00Z",
  match_group: "exact_match",
  rank_score: 0.99,
  variant_group_id: "vg1",
};

const variant = {
  ...product,
  id: "p2",
  title: "ASUS Vivobook 15 X1504VA 8GB 512GB",
  specs: { ...product.specs, ram_gb: 8, model_codes: ["X1504VA-8GB"] },
  best_price: 49990,
  match_group: "similar_variant",
  rank_score: 0.91,
};

const offers = [
  {
    id: "o1",
    platform: "Amazon India",
    listing_id: "amazon-p1",
    native_id: "ASINTEST",
    url: "https://www.amazon.in/dp/ASINTEST",
    title: product.title,
    image_url: null,
    price: 54990,
    mrp: 69990,
    effective_price: 54990,
    discount_percent: 21,
    currency: "INR",
    stock_status: "in_stock",
    rating: null,
    review_count: null,
    last_checked_at: "2026-07-18T12:00:00Z",
    last_verified_at: "2026-07-18T12:00:00Z",
    verification_status: "completed",
    verification_source: "metadata",
    next_allowed_verification_at: null,
    verification_failures: 0,
  },
  {
    id: "o2",
    platform: "Flipkart",
    listing_id: "flipkart-p1",
    native_id: "FLIPTEST",
    url: "https://www.flipkart.com/item/p/FLIPTEST",
    title: product.title,
    image_url: null,
    price: 55990,
    mrp: 69990,
    effective_price: 55990,
    discount_percent: 20,
    currency: "INR",
    stock_status: "in_stock",
    rating: null,
    review_count: null,
    last_checked_at: "2026-07-18T11:50:00Z",
    last_verified_at: "2026-07-18T11:50:00Z",
    verification_status: "completed",
    verification_source: "json-ld",
    next_allowed_verification_at: null,
    verification_failures: 0,
  },
];

function json(response, status, payload, requestId = "mock-request") {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "http://127.0.0.1:5173",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Headers": "Content-Type, X-Mayabu-Client-Id, X-Request-ID",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "X-Request-ID": requestId,
  });
  response.end(JSON.stringify(payload));
}

const server = http.createServer((request, response) => {
  if (!request.url) return json(response, 400, { detail: "Bad request" });
  if (request.method === "OPTIONS") return json(response, 204, {});
  const url = new URL(request.url, `http://127.0.0.1:${port}`);
  const requestId = request.headers["x-request-id"]?.toString() || "mock-request";

  if (url.pathname === "/api/health" || url.pathname === "/api/ready")
    return json(response, 200, { status: "ok" }, requestId);
  if (url.pathname === "/api/search") {
    const q = url.searchParams.get("q") || "";
    return json(
      response,
      200,
      {
        query: q,
        normalized_query: q.toLowerCase(),
        intent: "product_search",
        detected_category: "laptop",
        detected_brand: "ASUS",
        detected_specs: { ram_gb: 16 },
        result_count: 2,
        limit: 20,
        offset: 0,
        has_more: false,
        next_cursor: null,
        results: [product, variant],
        sections: { exact_matches: [product], similar_variants: [variant], related_products: [] },
        exact_match_count: 1,
        similar_variant_count: 1,
        related_product_count: 0,
        message: null,
      },
      requestId,
    );
  }
  if (url.pathname === "/api/products/p1")
    return json(
      response,
      200,
      {
        product,
        offers,
        offer_count: offers.length,
        similar_variants: [variant],
        similar_variant_count: 1,
      },
      requestId,
    );
  if (url.pathname === "/api/products/p2")
    return json(
      response,
      200,
      {
        product: variant,
        offers: [offers[1]],
        offer_count: 1,
        similar_variants: [product],
        similar_variant_count: 1,
      },
      requestId,
    );
  if (url.pathname === "/api/products/missing")
    return json(response, 404, { detail: "Product not found" }, requestId);
  if (url.pathname === "/api/products/p1/offers")
    return json(response, 200, { product_id: "p1", offers, offer_count: offers.length }, requestId);
  if (url.pathname === "/api/products/p1/price-history") {
    return json(
      response,
      200,
      {
        product_id: "p1",
        days: 180,
        history: [
          { date: "2026-06-01", best_price: 59990, best_platform: "Amazon India" },
          { date: "2026-06-20", best_price: 57990, best_platform: "Flipkart" },
          { date: "2026-07-18", best_price: 54990, best_platform: "Amazon India" },
        ],
      },
      requestId,
    );
  }
  if (url.pathname === "/api/products/p2/price-history")
    return json(response, 200, { product_id: "p2", days: 180, history: [] }, requestId);
  if (url.pathname === "/api/products/p1/verify-price" && request.method === "POST") {
    jobReads = 0;
    return json(
      response,
      202,
      {
        status: "queued",
        product_id: "p1",
        mode: "best_offer",
        task_ids: ["t1"],
        tasks: [{ task_id: "t1", listing_id: "o1", platform: "Amazon India", created: true }],
        skipped: [],
        estimated_seconds: 5,
        coalesced: false,
        message: "Verification queued",
      },
      requestId,
    );
  }
  if (url.pathname === "/api/verification-jobs/t1") {
    jobReads += 1;
    const status = jobReads < 2 ? "running" : "completed";
    return json(
      response,
      200,
      {
        task_id: "t1",
        status,
        platform: "Amazon India",
        attempts: 1,
        request_count: 1,
        result:
          status === "completed"
            ? { old_price: 54990, new_price: 54990, stock_status: "in_stock" }
            : {},
        last_error: null,
        created_at: "2026-07-18T12:00:00Z",
        updated_at: "2026-07-18T12:00:04Z",
      },
      requestId,
    );
  }
  if (url.pathname === "/api/products/p1/verification-status")
    return json(response, 200, { product_id: "p1", status: "completed" }, requestId);
  return json(response, 404, { detail: "Not found" }, requestId);
});

server.listen(port, "127.0.0.1", () => console.log(`Mayabu mock API listening on ${port}`));

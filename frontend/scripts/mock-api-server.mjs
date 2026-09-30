import http from "node:http";

const port = Number(process.env.MOCK_API_PORT || 8001);
let jobReads = 0;

const PUBLIC_CATEGORIES = [
  "laptop",
  "smartphone",
  "television",
  "refrigerator",
  "washing_machine",
  "tws",
  "headphones",
  "camera",
];

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
  display_specs: { ram_gb: 16, storage_gb: 512, screen_inch: 15.6, cpu_series: "Intel Core i5" },
  family: "Vivobook 15",
  model_codes: ["X1504VA"],
  best_price: 54990,
  best_platform: "amazon",
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
  display_specs: { ram_gb: 8, storage_gb: 512, screen_inch: 15.6 },
  best_price: 49990,
  match_group: "similar_variant",
  rank_score: 0.91,
};

const laptop3 = {
  ...product,
  id: "p3",
  title: "ASUS Vivobook 15 X1504VA 16GB 1TB",
  specs: { ...product.specs, storage_gb: 1024, model_codes: ["X1504VA-1TB"] },
  display_specs: { ram_gb: 16, storage_gb: 1024, screen_inch: 15.6 },
  best_price: 74990,
  match_group: "similar_variant",
  rank_score: 0.9,
};

const laptop4 = {
  ...product,
  id: "p4",
  title: "ASUS Vivobook 15 X1504VA 32GB 1TB",
  specs: { ...product.specs, ram_gb: 32, storage_gb: 1024, model_codes: ["X1504VA-32"] },
  display_specs: { ram_gb: 32, storage_gb: 1024, screen_inch: 15.6 },
  best_price: 89990,
  match_group: "similar_variant",
  rank_score: 0.89,
};

const phone = {
  id: "phone-1",
  title: "Samsung Galaxy S24 8GB 256GB",
  brand: "Samsung",
  category: "smartphone",
  specs: { ram_gb: 8, storage_gb: 256, network_generation: "5G" },
  display_specs: { ram_gb: 8, storage_gb: 256, network_generation: "5G" },
  family: "galaxy_s24",
  model_codes: ["SM-S921B"],
  best_price: 69990,
  best_platform: "flipkart",
  platform_count: 2,
  offer_count: 2,
  image_url: "https://rukminim2.flixcart.com/image/placeholder-phone.jpg",
  last_seen_at: "2026-07-18T12:00:00Z",
  match_group: "exact_match",
  rank_score: 0.95,
  variant_group_id: null,
};

const phone128 = {
  ...phone,
  id: "phone-2",
  title: "Samsung Galaxy S24 8GB 128GB",
  specs: { ...phone.specs, storage_gb: 128 },
  display_specs: { ram_gb: 8, storage_gb: 128, network_generation: "5G" },
  model_codes: ["SM-S921B-128"],
  best_price: 62990,
  offer_count: 1,
  platform_count: 1,
};

const tv = {
  id: "tv-1",
  title: "Samsung 55 inch 4K QLED Smart TV",
  brand: "Samsung",
  category: "television",
  specs: { screen_size_inch: 55, panel_type: "qled", resolution: "4k" },
  display_specs: { screen_size_inch: 55, panel_type: "qled", resolution: "4k" },
  best_price: 54990,
  best_platform: "croma",
  platform_count: 1,
  offer_count: 1,
  image_url: "https://media.croma.com/image/placeholder-tv.jpg",
  last_seen_at: "2026-07-18T12:00:00Z",
  match_group: "exact_match",
  rank_score: 0.9,
  variant_group_id: null,
};

const tv43 = {
  ...tv,
  id: "tv-2",
  title: "Samsung 43 inch 4K Crystal UHD Smart TV",
  specs: { screen_size_inch: 43, panel_type: "led", resolution: "4k" },
  display_specs: { screen_size_inch: 43, panel_type: "led", resolution: "4k" },
  best_price: 32990,
};

const washer = {
  id: "washer-1",
  title: "LG 8 Kg Front Load Washing Machine",
  brand: "LG",
  category: "washing_machine",
  specs: { capacity_kg: 8, load_type: "front_load", automation_type: "fully_automatic" },
  display_specs: { capacity_kg: 8, load_type: "front_load", automation_type: "fully_automatic" },
  best_price: 32990,
  best_platform: "reliancedigital",
  platform_count: 1,
  offer_count: 1,
  image_url: null,
  last_seen_at: "2026-07-18T12:00:00Z",
  match_group: "exact_match",
  rank_score: 0.88,
  variant_group_id: null,
};

const fridge = {
  id: "fridge-1",
  title: "LG 260L Frost Free Refrigerator",
  brand: "LG",
  category: "refrigerator",
  specs: { capacity_l: 260, door_type: "double_door", frost_type: "frost_free" },
  display_specs: { capacity_l: 260, door_type: "double_door", frost_type: "frost_free" },
  best_price: 24990,
  best_platform: "amazon",
  platform_count: 1,
  offer_count: 1,
  image_url: null,
  last_seen_at: "2026-07-18T12:00:00Z",
  match_group: "exact_match",
  rank_score: 0.87,
  variant_group_id: null,
};

const tws = {
  id: "tws-1",
  title: "Sony WF-1000XM5 ANC Earbuds",
  brand: "Sony",
  category: "tws",
  specs: { anc: true, form_factor: "in_ear", connectivity: "bluetooth" },
  display_specs: { anc: true, form_factor: "in_ear" },
  best_price: 19990,
  best_platform: "flipkart",
  platform_count: 2,
  offer_count: 2,
  image_url: null,
  last_seen_at: "2026-07-18T12:00:00Z",
  match_group: "exact_match",
  rank_score: 0.86,
  variant_group_id: null,
};

const headphones = {
  id: "hp-1",
  title: "Sony WH-1000XM5 Wireless Headphones",
  brand: "Sony",
  category: "headphones",
  specs: { anc: true, connectivity: "bluetooth", form_factor: "over_ear" },
  display_specs: { anc: true, form_factor: "over_ear" },
  best_price: 29990,
  best_platform: "croma",
  platform_count: 2,
  offer_count: 2,
  image_url: null,
  last_seen_at: "2026-07-18T12:00:00Z",
  match_group: "exact_match",
  rank_score: 0.85,
  variant_group_id: null,
};

const cameraBody = {
  id: "cam-1",
  title: "Sony Alpha A7 IV Body Only",
  brand: "Sony",
  category: "camera",
  specs: {
    camera_type: "mirrorless",
    sensor_format: "full_frame",
    megapixels: 33,
    mount: "e_mount",
    body_only: true,
  },
  display_specs: {
    camera_type: "mirrorless",
    sensor_format: "full_frame",
    megapixels: 33,
    mount: "e_mount",
    body_only: true,
  },
  model_codes: ["ILCE-7M4"],
  best_price: 189990,
  best_platform: "croma",
  platform_count: 2,
  offer_count: 2,
  image_url: null,
  last_seen_at: "2026-07-18T12:00:00Z",
  match_group: "exact_match",
  rank_score: 0.92,
  variant_group_id: "cam-a7iv",
};

const cameraKit = {
  id: "cam-2",
  title: "Sony Alpha A7 IV Kit 28-70mm",
  brand: "Sony",
  category: "camera",
  specs: {
    camera_type: "mirrorless",
    sensor_format: "full_frame",
    megapixels: 33,
    mount: "e_mount",
    body_only: false,
    kit_lens: "28-70mm",
  },
  display_specs: {
    camera_type: "mirrorless",
    megapixels: 33,
    body_only: false,
    kit_lens: "28-70mm",
  },
  model_codes: ["ILCE-7M4K"],
  best_price: 214990,
  best_platform: "vijaysales",
  platform_count: 1,
  offer_count: 1,
  image_url: null,
  last_seen_at: "2026-07-18T12:00:00Z",
  match_group: "similar_variant",
  rank_score: 0.9,
  variant_group_id: "cam-a7iv",
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
    last_checked_at: "2026-07-18T13:00:00Z",
    last_verified_at: "2026-07-18T08:00:00Z",
    verification_status: "failed",
    verification_source: "json-ld",
    next_allowed_verification_at: null,
    verification_failures: 1,
  },
];

const phoneOffers = [
  {
    id: "po1",
    platform: "flipkart",
    listing_id: "fk-phone-1",
    native_id: "PHONEFK",
    url: "https://www.flipkart.com/item/p/PHONEFK",
    title: phone.title,
    image_url: null,
    price: 69990,
    mrp: 79990,
    effective_price: 69990,
    discount_percent: 12,
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
    id: "po2",
    platform: "vijaysales",
    listing_id: "vs-phone-1",
    native_id: "PHONEVS",
    url: "https://www.vijaysales.com/product/PHONEVS",
    title: phone.title,
    image_url: null,
    price: 70990,
    mrp: 79990,
    effective_price: 70990,
    discount_percent: 11,
    currency: "INR",
    stock_status: "in_stock",
    rating: null,
    review_count: null,
    last_checked_at: "2026-07-18T10:00:00Z",
    last_verified_at: "2026-07-18T10:00:00Z",
    verification_status: "completed",
    verification_source: "metadata",
    next_allowed_verification_at: null,
    verification_failures: 0,
  },
  {
    id: "po3",
    platform: "poorvika",
    listing_id: "pv-phone-1",
    native_id: "PHONEPV",
    url: "https://www.poorvika.com/product/PHONEPV",
    title: phone.title,
    image_url: null,
    price: 71490,
    mrp: 79990,
    effective_price: 71490,
    discount_percent: 10,
    currency: "INR",
    stock_status: null,
    rating: null,
    review_count: null,
    last_checked_at: "2026-07-16T09:00:00Z",
    last_verified_at: "2026-07-16T09:00:00Z",
    verification_status: "completed",
    verification_source: "metadata",
    next_allowed_verification_at: null,
    verification_failures: 0,
  },
];

const tvOffers = [
  {
    id: "to1",
    platform: "croma",
    listing_id: "croma-tv-1",
    native_id: "TVCR",
    url: "https://www.croma.com/product/TVCR",
    title: tv.title,
    image_url: null,
    price: 54990,
    mrp: 69990,
    effective_price: 54990,
    discount_percent: 21,
    currency: "INR",
    stock_status: "in_stock",
    rating: null,
    review_count: null,
    last_checked_at: "2026-07-18T11:00:00Z",
    last_verified_at: "2026-07-18T11:00:00Z",
    verification_status: "completed",
    verification_source: "metadata",
    next_allowed_verification_at: null,
    verification_failures: 0,
  },
];

const cameraOffers = [
  {
    id: "co1",
    platform: "croma",
    listing_id: "croma-cam-1",
    native_id: "CAMCR",
    url: "https://www.croma.com/product/CAMCR",
    title: cameraBody.title,
    image_url: null,
    price: 189990,
    mrp: 219990,
    effective_price: 189990,
    discount_percent: 14,
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
    id: "co2",
    platform: "amazon",
    listing_id: "amazon-cam-1",
    native_id: "CAMAMZ",
    url: "https://www.amazon.in/dp/CAMAMZ",
    title: cameraBody.title,
    image_url: null,
    price: 192990,
    mrp: 219990,
    effective_price: 192990,
    discount_percent: 12,
    currency: "INR",
    stock_status: "in_stock",
    rating: null,
    review_count: null,
    last_checked_at: "2026-07-18T11:30:00Z",
    last_verified_at: "2026-07-18T11:30:00Z",
    verification_status: "completed",
    verification_source: "metadata",
    next_allowed_verification_at: null,
    verification_failures: 0,
  },
];

function detailPayload(item, itemOffers, similar = []) {
  const primary = item?.image_url || null;
  const images = [];
  if (primary) {
    images.push({ url: primary, is_primary: true, source: "mock" });
    // Second URL only when product already has a distinct gallery hint.
    if (item?.gallery_image_url && item.gallery_image_url !== primary) {
      images.push({ url: item.gallery_image_url, is_primary: false, source: "mock" });
    } else if (typeof primary === "string" && primary.includes("cdn.example.com")) {
      images.push({
        url: primary.replace(/(\.\w+)$/, "-alt$1"),
        is_primary: false,
        source: "mock",
      });
    }
  }
  return {
    product: item,
    offers: itemOffers,
    offer_count: itemOffers.length,
    similar_variants: similar,
    similar_variant_count: similar.length,
    images,
    image_count: images.length,
  };
}

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

function searchPayload(q, extras = {}) {
  return {
    query: q,
    normalized_query: q.toLowerCase(),
    intent: "product_search",
    detected_category: extras.detected_category ?? "laptop",
    detected_brand: extras.detected_brand ?? null,
    detected_specs: extras.detected_specs ?? {},
    search_mode: extras.search_mode ?? "category",
    category_confidence: "high",
    public_categories: PUBLIC_CATEGORIES,
    search_contract_version: "v6",
    result_count: extras.results?.length ?? 2,
    limit: 20,
    offset: Number(extras.offset ?? 0),
    has_more: Boolean(extras.has_more),
    next_cursor: null,
    results: extras.results ?? [product, variant],
    sections: extras.sections ?? {
      exact_matches: [product],
      similar_variants: [variant],
      related_products: [],
    },
    exact_match_count: extras.sections?.exact_matches?.length ?? 1,
    similar_variant_count: extras.sections?.similar_variants?.length ?? 1,
    related_product_count: extras.sections?.related_products?.length ?? 0,
    facets: extras.facets ?? {
      brand: [
        { value: "asus", count: 2 },
        { value: "hp", count: 1 },
      ],
      ram_gb: [
        { value: "8", count: 1 },
        { value: "16", count: 2 },
      ],
      storage_gb: [{ value: "512", count: 2 }],
    },
    facet_scope: "query",
    category_counts: extras.category_counts ?? { laptop: 2 },
    sort: extras.sort ?? "relevance",
    min_price: extras.min_price ?? null,
    max_price: extras.max_price ?? null,
    message: null,
  };
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => resolve(Buffer.concat(chunks).toString("utf8") || "{}"));
    request.on("error", reject);
  });
}

const server = http.createServer(async (request, response) => {
  if (!request.url) return json(response, 400, { detail: "Bad request" });
  if (request.method === "OPTIONS") return json(response, 204, {});
  const url = new URL(request.url, `http://127.0.0.1:${port}`);
  const requestId = request.headers["x-request-id"]?.toString() || "mock-request";

  if (url.pathname === "/api/health" || url.pathname === "/api/ready")
    return json(response, 200, { status: "ok" }, requestId);

  if (url.pathname === "/api/seo/sitemap/meta") {
    const pageSize = Number(url.searchParams.get("page_size") || 5000);
    const items = [product, phone, tv, fridge, washer, tws, headphones, cameraBody];
    const pages = Math.max(1, Math.ceil(items.length / pageSize));
    return json(
      response,
      200,
      {
        contract_version: "v1",
        total: items.length,
        page_size: pageSize,
        pages,
        max_urls_per_sitemap: 45000,
      },
      requestId,
    );
  }

  if (url.pathname === "/api/seo/sitemap/products") {
    const page = Math.max(1, Number(url.searchParams.get("page") || 1));
    const pageSize = Number(url.searchParams.get("page_size") || 5000);
    const all = [product, phone, tv, fridge, washer, tws, headphones, cameraBody].map((item) => ({
      product_id: item.id,
      title: item.title,
      lastmod: item.last_seen_at || "2026-07-18T12:00:00Z",
    }));
    const start = (page - 1) * pageSize;
    const slice = all.slice(start, start + pageSize);
    return json(
      response,
      200,
      { page, page_size: pageSize, count: slice.length, items: slice, contract_version: "v1" },
      requestId,
    );
  }

  const categoryLandingMatch = url.pathname.match(/^\/api\/categories\/([^/]+)\/landing$/);
  if (categoryLandingMatch) {
    const category = decodeURIComponent(categoryLandingMatch[1]);
    const byCategory = {
      laptop: [product, variant, laptop3, laptop4],
      smartphone: [phone, phone128],
      television: [tv, tv43],
      refrigerator: [fridge],
      washing_machine: [washer],
      tws: [tws],
      headphones: [headphones],
      camera: [cameraBody],
    };
    const products = byCategory[category];
    if (!products) return json(response, 400, { detail: "Invalid category." }, requestId);
    const facets =
      category === "laptop"
        ? {
            brand: [{ value: "asus", count: products.length }],
            ram_gb: [
              { value: "16", count: 3 },
              { value: "8", count: 1 },
            ],
            storage_gb: [
              { value: "512", count: 2 },
              { value: "1024", count: 2 },
            ],
          }
        : category === "smartphone"
          ? {
              brand: [{ value: "samsung", count: 2 }],
              ram_gb: [{ value: "8", count: 2 }],
              storage_gb: [
                { value: "256", count: 1 },
                { value: "128", count: 1 },
              ],
            }
          : category === "camera"
            ? {
                brand: [{ value: "sony", count: 1 }],
                body_only: [{ value: "true", count: 1 }],
              }
            : {
                brand: [
                  {
                    value: String(products[0]?.brand || "brand").toLowerCase(),
                    count: products.length,
                  },
                ],
              };
    return json(
      response,
      200,
      {
        category,
        display_name: category,
        featured: products.slice(0, 4),
        products,
        facets,
        facet_keys: Object.keys(facets),
        price_drops: products.slice(0, 1).map((item) => ({
          ...item,
          previous_price: Number(item.best_price) + 5000,
          drop_amount: 5000,
          drop_percent: 8,
          drop_window_days: 30,
        })),
        biggest_discounts: products.slice(0, 1).map((item) => ({
          ...item,
          mrp: Number(item.best_price) + 10000,
          discount_percent: 12,
          discount_amount: 10000,
        })),
        lowest_since_tracking: [],
        trending: [],
        popular: products.slice(0, 1),
        related_categories: PUBLIC_CATEGORIES.filter((slug) => slug !== category).slice(0, 4),
        semantics: {},
        contract_version: "v1",
      },
      requestId,
    );
  }

  if (url.pathname === "/api/homepage") {
    return json(
      response,
      200,
      {
        trending: [],
        popular: [],
        recently_checked: [
          { ...phone, image_url: phone.image_url },
          { ...product, image_url: "https://cdn.example.com/laptop.jpg" },
          { ...tv, image_url: tv.image_url },
          { ...cameraBody, image_url: "https://media.croma.com/image/placeholder-camera.jpg" },
          {
            ...washer,
            id: "p-fill-5",
            title: "LG 8 Kg Front Load Washing Machine",
            image_url: "https://cdn.example.com/washer.jpg",
          },
          {
            ...fridge,
            id: "p-fill-6",
            title: "LG 260L Frost Free Refrigerator",
            image_url: "https://cdn.example.com/fridge.jpg",
          },
        ],
        price_drops: [
          {
            ...product,
            id: "drop-1",
            best_price: 54990,
            previous_price: 59990,
            drop_amount: 5000,
            drop_percent: 8,
            drop_window_days: 30,
            image_url: "https://cdn.example.com/laptop.jpg",
          },
          {
            ...phone,
            id: "drop-2",
            best_price: 64990,
            previous_price: 74990,
            drop_amount: 10000,
            drop_percent: 13,
            drop_window_days: 14,
          },
        ],
        biggest_discounts: [
          {
            ...phone,
            id: "disc-1",
            best_price: 69990,
            mrp: 79990,
            discount_percent: 12,
            discount_amount: 10000,
          },
          {
            ...tv,
            id: "disc-2",
            best_price: 54990,
            mrp: 69990,
            discount_percent: 21,
            discount_amount: 15000,
          },
          {
            ...washer,
            id: "disc-3",
            best_price: 32990,
            mrp: 42990,
            discount_percent: 23,
            discount_amount: 10000,
            image_url: "https://cdn.example.com/washer.jpg",
          },
          {
            ...fridge,
            id: "disc-4",
            best_price: 24990,
            mrp: 31990,
            discount_percent: 22,
            discount_amount: 7000,
            image_url: "https://cdn.example.com/fridge.jpg",
          },
        ],
        lowest_since_tracking: [
          {
            ...cameraBody,
            id: "low-1",
            best_price: 89990,
            tracked_low_price: 89990,
            is_lowest_since_tracking: true,
            tracking_observation_count: 4,
            tracking_day_count: 3,
            image_url: "https://media.croma.com/image/placeholder-camera.jpg",
          },
          {
            ...product,
            id: "low-2",
            best_price: 52990,
            tracked_low_price: 52990,
            is_lowest_since_tracking: true,
            tracking_observation_count: 5,
            tracking_day_count: 4,
            image_url: "https://cdn.example.com/laptop.jpg",
          },
          {
            ...phone,
            id: "low-3",
            best_price: 67990,
            tracked_low_price: 67990,
            is_lowest_since_tracking: true,
            tracking_observation_count: 6,
            tracking_day_count: 5,
          },
          {
            ...tv,
            id: "low-4",
            best_price: 51990,
            tracked_low_price: 51990,
            is_lowest_since_tracking: true,
            tracking_observation_count: 3,
            tracking_day_count: 3,
          },
        ],
        featured: [
          { ...product, image_url: "https://cdn.example.com/laptop.jpg" },
          phone,
          tv,
          { ...cameraBody, image_url: "https://media.croma.com/image/placeholder-camera.jpg" },
          {
            ...washer,
            id: "feat-5",
            image_url: "https://cdn.example.com/washer.jpg",
          },
          {
            ...fridge,
            id: "feat-6",
            image_url: "https://cdn.example.com/fridge.jpg",
          },
        ],
        multi_store: [
          {
            ...phone,
            id: "multi-1",
            platform_count: 4,
            offer_count: 4,
            best_price: 69990,
          },
          {
            ...product,
            id: "multi-2",
            platform_count: 3,
            offer_count: 3,
            best_price: 54990,
            image_url: "https://cdn.example.com/laptop.jpg",
          },
          {
            ...tv,
            id: "multi-3",
            platform_count: 3,
            offer_count: 3,
            best_price: 54990,
          },
        ],
        near_tracked_low: [
          {
            ...headphones,
            id: "near-1",
            best_price: 24990,
            tracked_low_price: 23990,
            near_tracked_low: true,
            near_low_gap_percent: 4.2,
            tracking_observation_count: 12,
            tracking_day_count: 21,
          },
          {
            ...tws,
            id: "near-2",
            best_price: 1999,
            tracked_low_price: 1899,
            near_tracked_low: true,
            near_low_gap_percent: 5.0,
            tracking_observation_count: 10,
            tracking_day_count: 16,
          },
        ],
        explore_by_category: [
          { slug: "smartphone", label: "Smartphones", products: [phone, phone128].filter(Boolean).slice(0, 3) },
          { slug: "laptop", label: "Laptops", products: [product, variant].filter(Boolean).slice(0, 3) },
          { slug: "television", label: "Televisions", products: [tv].slice(0, 3) },
          { slug: "headphones", label: "Headphones", products: [headphones].slice(0, 3) },
          { slug: "camera", label: "Cameras", products: [cameraBody, cameraKit].filter(Boolean).slice(0, 3) },
          { slug: "washing_machine", label: "Washing Machines", products: [washer].slice(0, 3) },
          { slug: "refrigerator", label: "Refrigerators", products: [fridge].slice(0, 3) },
          { slug: "tws", label: "TWS", products: [tws].slice(0, 3) },
        ],
        category_spotlights: [
          {
            slug: "smartphone",
            title: "Smartphone picks to compare",
            description: "Current public prices across phone variants.",
            products: [phone, phone128].filter(Boolean),
          },
          {
            slug: "television",
            title: "TVs worth tracking",
            description: "Screen sizes and panels with live Mayabu prices.",
            products: [tv, tv43].filter(Boolean),
          },
        ],
        categories: PUBLIC_CATEGORIES,
        stores: [],
        semantics: {
          recently_checked: "Most recent verified price observations.",
          price_drops: "Current best price lower than a prior daily observation within 30 days.",
          biggest_discounts: "Validated listing MRP above current public offer price.",
          lowest_since_tracking: "Current best price at Mayabu tracked low.",
          near_tracked_low: "Current best price within 5% of Mayabu tracked minimum.",
          multi_store: "Products currently available from multiple supported stores.",
          explore_by_category: "Bounded samples from each public Mayabu category.",
          category_spotlights: "Deterministic category spotlights when supply allows.",
          trending: null,
          trending_note: "Trending hidden until enough engagement exists.",
          popular: null,
        },
      },
      requestId,
    );
  }
  if (url.pathname === "/api/activity" && request.method === "POST") {
    return json(response, 200, { accepted: true, deduped: false }, requestId);
  }
  if (url.pathname === "/api/search/suggest") {
    const q = (url.searchParams.get("q") || "").trim();
    const ql = q.toLowerCase();
    const categories = [];
    const products = [];
    if (!q || q.length < 2) {
      return json(
        response,
        200,
        {
          query: q,
          products: [],
          categories: [
            { slug: "laptop", label: "Laptops" },
            { slug: "smartphone", label: "Smartphones" },
            { slug: "television", label: "TVs" },
          ],
          // Threshold-qualified aggregates only — mock mirrors privacy floor.
          popular_queries: [
            { query: "samsung galaxy", hits: 12 },
            { query: "gaming laptop", hits: 9 },
          ],
          search_contract_version: "v2",
        },
        requestId,
      );
    }
    if (
      ql.includes("phone") ||
      ql.includes("galaxy") ||
      ql.includes("s24") ||
      ql.includes("samsung") ||
      ql.startsWith("sam")
    ) {
      products.push({
        id: phone.id,
        title: phone.title,
        brand: phone.brand,
        category: phone.category,
        image_url: phone.image_url,
        best_price: phone.best_price,
        best_platform: phone.best_platform,
        offer_count: phone.offer_count,
        display_specs: phone.display_specs || {},
        specs: phone.specs || {},
        model_codes: phone.model_codes || [],
      });
      categories.push({ slug: "smartphone", label: "Smartphones" });
    } else if (ql.includes("laptop") || ql.includes("macbook") || ql.includes("thinkpad") || ql.includes("asus")) {
      products.push({
        id: product.id,
        title: product.title,
        brand: product.brand,
        category: product.category,
        image_url: product.image_url,
        best_price: product.best_price,
        best_platform: product.best_platform,
        offer_count: product.offer_count,
        display_specs: product.display_specs || {},
        specs: product.specs || {},
        model_codes: product.model_codes || [],
      });
      categories.push({ slug: "laptop", label: "Laptops" });
    } else if (ql.includes("tv") || ql.includes("oled") || ql.includes("sony")) {
      if (ql.includes("sony") || ql.includes("camera") || ql.includes("alpha")) {
        products.push({
          id: cameraBody.id,
          title: cameraBody.title,
          brand: cameraBody.brand,
          category: cameraBody.category,
          image_url: cameraBody.image_url,
          best_price: cameraBody.best_price,
          best_platform: cameraBody.best_platform,
          offer_count: cameraBody.offer_count,
          display_specs: cameraBody.display_specs || {},
          specs: cameraBody.specs || {},
          model_codes: cameraBody.model_codes || [],
        });
        categories.push({ slug: "camera", label: "Cameras" });
      } else {
        products.push({
          id: tv.id,
          title: tv.title,
          brand: tv.brand,
          category: tv.category,
          image_url: tv.image_url,
          best_price: tv.best_price,
          best_platform: tv.best_platform,
          offer_count: tv.offer_count,
          display_specs: tv.display_specs || {},
          specs: tv.specs || {},
          model_codes: tv.model_codes || [],
        });
        categories.push({ slug: "television", label: "TVs" });
      }
    }
    return json(
      response,
      200,
      {
        query: q,
        products,
        categories,
        popular_queries: [],
        search_contract_version: "v2",
      },
      requestId,
    );
  }
  if (url.pathname === "/api/search") {
    const q = url.searchParams.get("q") || "";
    const category = url.searchParams.get("category") || "";
    const sort = url.searchParams.get("sort") || "relevance";
    const filtersRaw = url.searchParams.get("filters") || "";
    if (filtersRaw.includes("camera_mp")) {
      return json(
        response,
        400,
        { detail: "Invalid filters: unsupported_filter:camera_mp" },
        requestId,
      );
    }
    const ql = q.toLowerCase();

    if (ql.includes("galaxy") || category === "smartphone") {
      return json(
        response,
        200,
        searchPayload(q, {
          detected_category: "smartphone",
          detected_brand: "Samsung",
          results: [phone],
          sections: { exact_matches: [phone], similar_variants: [], related_products: [] },
          facets: {
            brand: [{ value: "samsung", count: 1 }],
            ram_gb: [{ value: "8", count: 1 }],
            storage_gb: [{ value: "256", count: 1 }],
          },
          category_counts: { smartphone: 1 },
          sort,
        }),
        requestId,
      );
    }
    if (ql.includes("tv") || ql.includes("oled") || category === "television") {
      return json(
        response,
        200,
        searchPayload(q, {
          detected_category: "television",
          detected_brand: "Samsung",
          results: [tv],
          sections: { exact_matches: [tv], similar_variants: [], related_products: [] },
          facets: {
            brand: [{ value: "samsung", count: 1 }],
            screen_size_inch: [{ value: "55", count: 1 }],
            panel_type: [{ value: "qled", count: 1 }],
          },
          category_counts: { television: 1 },
          sort,
        }),
        requestId,
      );
    }
    if (ql.includes("washing") || ql.includes("front load") || category === "washing_machine") {
      return json(
        response,
        200,
        searchPayload(q, {
          detected_category: "washing_machine",
          detected_brand: "LG",
          results: [washer],
          sections: { exact_matches: [washer], similar_variants: [], related_products: [] },
          facets: {
            brand: [{ value: "lg", count: 1 }],
            capacity_kg: [{ value: "8", count: 1 }],
            load_type: [{ value: "front_load", count: 1 }],
          },
          category_counts: { washing_machine: 1 },
          sort,
        }),
        requestId,
      );
    }
    if (ql.includes("refrigerator") || ql.includes("260") || category === "refrigerator") {
      return json(
        response,
        200,
        searchPayload(q, {
          detected_category: "refrigerator",
          detected_brand: "LG",
          results: [fridge],
          sections: { exact_matches: [fridge], similar_variants: [], related_products: [] },
          facets: {
            brand: [{ value: "lg", count: 1 }],
            capacity_l: [{ value: "260", count: 1 }],
            door_type: [{ value: "double_door", count: 1 }],
          },
          category_counts: { refrigerator: 1 },
          sort,
        }),
        requestId,
      );
    }
    if (
      ql.includes("earbuds") ||
      ql.includes("tws") ||
      ql.includes("wf-1000") ||
      category === "tws"
    ) {
      return json(
        response,
        200,
        searchPayload(q, {
          detected_category: "tws",
          detected_brand: "Sony",
          results: [tws],
          sections: { exact_matches: [tws], similar_variants: [], related_products: [] },
          facets: {
            brand: [{ value: "sony", count: 1 }],
            anc: [{ value: "true", count: 1 }],
          },
          category_counts: { tws: 1 },
          sort,
        }),
        requestId,
      );
    }
    if (ql.includes("headphones") || ql.includes("wh-1000") || category === "headphones") {
      return json(
        response,
        200,
        searchPayload(q, {
          detected_category: "headphones",
          detected_brand: "Sony",
          results: [headphones],
          sections: { exact_matches: [headphones], similar_variants: [], related_products: [] },
          facets: {
            brand: [{ value: "sony", count: 1 }],
            anc: [{ value: "true", count: 1 }],
          },
          category_counts: { headphones: 1 },
          sort,
        }),
        requestId,
      );
    }
    if (
      ql === "samsung" ||
      (ql.includes("samsung") && !ql.includes("galaxy") && !ql.includes("tv"))
    ) {
      return json(
        response,
        200,
        searchPayload(q, {
          detected_category: null,
          detected_brand: "Samsung",
          search_mode: "cross_category",
          results: [phone, tv],
          sections: {
            exact_matches: [],
            similar_variants: [],
            related_products: [phone, tv],
          },
          facets: { brand: [{ value: "samsung", count: 2 }] },
          category_counts: { smartphone: 1, television: 1 },
          sort,
        }),
        requestId,
      );
    }

    return json(
      response,
      200,
      searchPayload(q, {
        detected_category: category || "laptop",
        detected_brand: "ASUS",
        detected_specs: { ram_gb: 16 },
        sort,
        offset: url.searchParams.get("offset") || 0,
      }),
      requestId,
    );
  }
  if (url.pathname === "/api/compare") {
    const byId = new Map([
      ["p1", { ...product, offer_count: 2 }],
      ["p2", { ...variant, offer_count: 1 }],
      ["p3", { ...laptop3, offer_count: 1 }],
      ["p4", { ...laptop4, offer_count: 2 }],
      ["phone-1", { ...phone, offer_count: phoneOffers.length }],
      ["phone-2", { ...phone128, offer_count: 1 }],
      ["tv-1", { ...tv, offer_count: 1 }],
      ["tv-2", { ...tv43, offer_count: 1 }],
      ["washer-1", { ...washer, offer_count: 1 }],
      ["fridge-1", { ...fridge, offer_count: 1 }],
      ["cam-1", { ...cameraBody, offer_count: 2 }],
      ["cam-2", { ...cameraKit, offer_count: 1 }],
      ["tws-1", { ...tws, offer_count: 1 }],
      ["hp-1", { ...headphones, offer_count: 1 }],
    ]);
    const raw = url.searchParams.get("ids") || "";
    const seen = new Set();
    const requested = [];
    for (const part of raw.split(",")) {
      const id = part.trim();
      if (!id || seen.has(id)) continue;
      seen.add(id);
      requested.push(id);
      if (requested.length >= 4) break;
    }
    const productsOut = [];
    const missing_ids = [];
    const skipped = [];
    let category = null;
    const warnings = [];
    for (const id of requested) {
      const item = byId.get(id);
      if (!item) {
        missing_ids.push(id);
        continue;
      }
      const cat = (item.category || "").toLowerCase();
      if (!category) category = cat;
      else if (cat !== category) {
        skipped.push({ id, reason: "category_mismatch", category: cat });
        warnings.push("category_mismatch");
        continue;
      }
      productsOut.push(item);
    }
    return json(
      response,
      200,
      {
        products: productsOut,
        category,
        requested_ids: requested,
        missing_ids,
        skipped,
        warnings: [...new Set(warnings)],
      },
      requestId,
    );
  }
  if (url.pathname === "/api/products/p1")
    return json(response, 200, detailPayload(product, offers, [variant]), requestId);
  if (url.pathname === "/api/products/p2")
    return json(response, 200, detailPayload(variant, [offers[1]], [product]), requestId);
  if (url.pathname === "/api/products/phone-1")
    return json(response, 200, detailPayload(phone, phoneOffers), requestId);
  if (url.pathname === "/api/products/tv-1")
    return json(response, 200, detailPayload(tv, tvOffers), requestId);
  if (url.pathname === "/api/products/washer-1")
    return json(
      response,
      200,
      detailPayload(washer, [
        {
          ...tvOffers[0],
          id: "wo1",
          platform: "reliancedigital",
          url: "https://www.reliancedigital.in/product/WASHER",
          title: washer.title,
          price: 32990,
          mrp: 39990,
          effective_price: 32990,
        },
      ]),
      requestId,
    );
  if (url.pathname === "/api/products/fridge-1")
    return json(
      response,
      200,
      detailPayload(fridge, [
        {
          ...tvOffers[0],
          id: "fo1",
          platform: "amazon",
          url: "https://www.amazon.in/dp/FRIDGE",
          title: fridge.title,
          price: 24990,
          mrp: 29990,
          effective_price: 24990,
        },
      ]),
      requestId,
    );
  if (url.pathname === "/api/products/tws-1")
    return json(
      response,
      200,
      detailPayload(tws, [
        {
          ...phoneOffers[0],
          id: "tws-o1",
          title: tws.title,
          price: 19990,
          mrp: 24990,
          effective_price: 19990,
        },
        {
          ...phoneOffers[1],
          id: "tws-o2",
          title: tws.title,
          price: 20490,
          mrp: 24990,
          effective_price: 20490,
        },
      ]),
      requestId,
    );
  if (url.pathname === "/api/products/hp-1")
    return json(
      response,
      200,
      detailPayload(headphones, [
        {
          ...tvOffers[0],
          id: "hp-o1",
          title: headphones.title,
          price: 29990,
          mrp: 34990,
          effective_price: 29990,
        },
      ]),
      requestId,
    );
  if (url.pathname === "/api/products/cam-1")
    return json(response, 200, detailPayload(cameraBody, cameraOffers, [cameraKit]), requestId);
  if (url.pathname === "/api/products/cam-2")
    return json(
      response,
      200,
      detailPayload(
        cameraKit,
        [
          {
            ...cameraOffers[0],
            id: "ck1",
            platform: "vijaysales",
            url: "https://www.vijaysales.com/product/CAMKIT",
            title: cameraKit.title,
            price: 214990,
            mrp: 239990,
            effective_price: 214990,
          },
        ],
        [cameraBody],
      ),
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
        days: 3650,
        window: "all",
        history: [
          { date: "2026-06-01", best_price: 59990, best_platform: "Amazon India" },
          { date: "2026-06-03", best_price: 58990, best_platform: "Amazon India" },
          { date: "2026-07-18", best_price: 54990, best_platform: "Amazon India" },
        ],
        best_price: [
          { date: "2026-06-01", price: 59990, observed: true },
          { date: "2026-06-03", price: 58990, observed: true },
          { date: "2026-07-18", price: 54990, observed: true },
        ],
        platforms: {
          amazon: [
            { date: "2026-06-01", price: 59990, observed: true },
            { date: "2026-06-03", price: 58990, observed: true },
            { date: "2026-07-18", price: 54990, observed: true },
          ],
          flipkart: [{ date: "2026-06-20", price: 57990, observed: true }],
        },
        missing_days_are_unobserved: true,
      },
      requestId,
    );
  }
  if (url.pathname.endsWith("/price-intelligence")) {
    const productId = url.pathname.split("/")[3];
    return json(
      response,
      200,
      {
        product_id: productId,
        current: { price: 54990, platform: "amazon" },
        freshness: { hours: 0.2 },
        store_coverage: { store_count: 3, in_stock_count: 3 },
        history_summary: {
          observation_count: 40,
          tracking_days: 90,
          tracked_low: 52990,
          tracked_high: 61990,
        },
        windows: {
          "30d": { window: "30d", observation_days: 20, tracking_days: 30, low: 53999, high: 59990 },
          "90d": { window: "90d", observation_days: 40, tracking_days: 90, low: 53999, high: 61990 },
          tracked: { window: "tracked", observation_days: 40, tracking_days: 90, low: 52990, high: 61990 },
        },
        timing_signal: {
          state: "CONSIDER_NOW",
          label: "Consider now",
          reasons: ["₹54,990 is within 2% of the lowest price Mayabu has tracked over the last 90 days."],
          reason_codes: ["NEAR_RECENT_LOW", "MULTI_STORE", "FRESH"],
          window: "90d",
          freshness_hours: 0.2,
          store_count: 3,
          in_stock_count: 3,
          purchasability: "in_stock",
        },
        reasons: ["₹54,990 is within 2% of the lowest price Mayabu has tracked over the last 90 days."],
        reason_codes: ["NEAR_RECENT_LOW", "MULTI_STORE", "FRESH"],
        signal: "CONSIDER_NOW",
        purchasability: "in_stock",
        platform_summary: { amazon: { observation_days: 20, low: 54990 }, flipkart: { observation_days: 18, low: 57990 } },
        disclosure: "Mayabu compares the current public price with prices it has observed over time.",
      },
      requestId,
    );
  }
  if (url.pathname === "/api/products/phone-1/price-history")
    return json(
      response,
      200,
      {
        product_id: "phone-1",
        days: 180,
        history: [
          { date: "2026-06-01", best_price: 74990 },
          { date: "2026-07-01", best_price: 71990 },
          { date: "2026-07-18", best_price: 69990 },
        ],
      },
      requestId,
    );
  if (url.pathname === "/api/products/tv-1/price-history")
    return json(response, 200, { product_id: "tv-1", days: 180, history: [] }, requestId);
  if (url.pathname === "/api/products/cam-1/price-history")
    return json(
      response,
      200,
      {
        product_id: "cam-1",
        days: 180,
        history: [
          { date: "2026-06-10", best_price: 199990 },
          { date: "2026-07-18", best_price: 189990 },
        ],
      },
      requestId,
    );
  if (url.pathname.endsWith("/price-history")) {
    const productId = url.pathname.split("/")[3];
    return json(response, 200, { product_id: productId, days: 180, history: [] }, requestId);
  }
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

  // --- Auth / wishlist (in-memory for E2E) ---
  const cookies = Object.fromEntries(
    (request.headers.cookie || "")
      .split(";")
      .map((part) => part.trim().split("="))
      .filter((pair) => pair.length === 2)
      .map(([k, v]) => [k, decodeURIComponent(v)]),
  );
  if (url.pathname === "/api/auth/csrf") {
    const token = cookies.mayabu_csrf || `csrf-${Date.now()}`;
    response.setHeader(
      "Set-Cookie",
      `mayabu_csrf=${encodeURIComponent(token)}; Path=/; SameSite=Lax`,
    );
    return json(response, 200, { csrf_token: token }, requestId);
  }
  if (url.pathname === "/api/auth/me") {
    const session = cookies.mayabu_session;
    const user = session ? globalThis.__mayabuUsers?.get(session) : null;
    return json(
      response,
      200,
      {
        user: user
          ? {
              id: user.id,
              email: user.email,
              display_name: user.display_name,
              email_verified: Boolean(user.email_verified),
              created_at: user.created_at,
            }
          : null,
        wishlist_count: user ? (globalThis.__mayabuWishlist?.get(user.id)?.size ?? 0) : 0,
      },
      requestId,
    );
  }
  if (url.pathname === "/api/auth/register" && request.method === "POST") {
    const body = JSON.parse(await readBody(request));
    globalThis.__mayabuUsers ||= new Map();
    globalThis.__mayabuWishlist ||= new Map();
    const id = `u-${globalThis.__mayabuUsers.size + 1}`;
    const session = `sess-${id}`;
    const user = {
      id,
      email: String(body.email || "").toLowerCase(),
      display_name: body.display_name || null,
      email_verified: false,
      created_at: new Date().toISOString(),
      password: String(body.password || ""),
    };
    globalThis.__mayabuUsers.set(session, user);
    globalThis.__mayabuWishlist.set(id, new Set());
    response.setHeader(
      "Set-Cookie",
      `mayabu_session=${encodeURIComponent(session)}; Path=/; HttpOnly; SameSite=Lax`,
    );
    response.appendHeader(
      "Set-Cookie",
      `mayabu_csrf=${encodeURIComponent(cookies.mayabu_csrf || "csrf")}; Path=/; SameSite=Lax`,
    );
    return json(
      response,
      200,
      {
        user: {
          id: user.id,
          email: user.email,
          display_name: user.display_name,
          email_verified: false,
          created_at: user.created_at,
        },
        verification_email_queued: true,
        message: "Account created.",
      },
      requestId,
    );
  }
  if (url.pathname === "/api/auth/login" && request.method === "POST") {
    const body = JSON.parse(await readBody(request));
    const email = String(body.email || "").toLowerCase();
    const password = String(body.password || "");
    let found = null;
    let sessionKey = null;
    for (const [session, user] of globalThis.__mayabuUsers || []) {
      if (user.email === email && user.password === password) {
        found = user;
        sessionKey = session;
        break;
      }
    }
    if (!found) return json(response, 401, { detail: "Invalid email or password." }, requestId);
    response.setHeader(
      "Set-Cookie",
      `mayabu_session=${encodeURIComponent(sessionKey)}; Path=/; HttpOnly; SameSite=Lax`,
    );
    return json(
      response,
      200,
      {
        user: {
          id: found.id,
          email: found.email,
          display_name: found.display_name,
          email_verified: Boolean(found.email_verified),
          created_at: found.created_at,
        },
      },
      requestId,
    );
  }
  if (url.pathname === "/api/auth/logout" && request.method === "POST") {
    response.setHeader("Set-Cookie", "mayabu_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax");
    return json(response, 200, { status: "ok" }, requestId);
  }
  if (url.pathname === "/api/wishlist" && request.method === "GET") {
    const session = cookies.mayabu_session;
    const user = session ? globalThis.__mayabuUsers?.get(session) : null;
    if (!user) return json(response, 401, { detail: "Authentication required" }, requestId);
    const ids = [...(globalThis.__mayabuWishlist?.get(user.id) || [])];
    const watches = globalThis.__mayabuWatch?.get(user.id) || new Map();
    const catalog = {
      p1: product,
      p2: variant,
      "phone-1": phone,
      "tv-1": tv,
      "cam-1": cameraBody,
      "washer-1": washer,
    };
    const products = ids
      .map((id) => {
        const base = catalog[id];
        if (!base) return null;
        const watch = watches.get(id) || {};
        return {
          ...base,
          offer_count: base.offer_count || 1,
          available: true,
          target_price: watch.target_price ?? null,
          notify_on_drop: Boolean(watch.notify_on_drop),
          watch_delivery: "deferred",
        };
      })
      .filter(Boolean);
    return json(
      response,
      200,
      { products, count: products.length, recent_watch_activity: [], watch_delivery: "deferred" },
      requestId,
    );
  }
  if (url.pathname.startsWith("/api/wishlist/") && request.method === "PATCH") {
    const session = cookies.mayabu_session;
    const user = session ? globalThis.__mayabuUsers?.get(session) : null;
    if (!user) return json(response, 401, { detail: "Authentication required" }, requestId);
    const productId = url.pathname.split("/").pop();
    const body = JSON.parse(await readBody(request));
    const target = body.target_price;
    if (target != null && (Number(target) <= 0 || Number(target) > 10_000_000)) {
      return json(response, 422, { detail: "target_price_out_of_range" }, requestId);
    }
    globalThis.__mayabuWishlist ||= new Map();
    globalThis.__mayabuWatch ||= new Map();
    const set = globalThis.__mayabuWishlist.get(user.id) || new Set();
    set.add(productId);
    globalThis.__mayabuWishlist.set(user.id, set);
    const watches = globalThis.__mayabuWatch.get(user.id) || new Map();
    watches.set(productId, {
      target_price: target == null ? null : Number(target),
      notify_on_drop: Boolean(body.notify_on_drop),
    });
    globalThis.__mayabuWatch.set(user.id, watches);
    const saved = watches.get(productId);
    return json(
      response,
      200,
      {
        status: "updated",
        product_id: productId,
        target_price: saved.target_price,
        notify_on_drop: saved.notify_on_drop,
        watch_delivery: "deferred",
        message: "Watch saved. Mayabu tracks this price inside your account.",
        count: set.size,
      },
      requestId,
    );
  }
  if (url.pathname.startsWith("/api/wishlist/") && request.method === "POST") {
    const session = cookies.mayabu_session;
    const user = session ? globalThis.__mayabuUsers?.get(session) : null;
    if (!user) return json(response, 401, { detail: "Authentication required" }, requestId);
    const productId = url.pathname.split("/").pop();
    const set = globalThis.__mayabuWishlist.get(user.id) || new Set();
    const existed = set.has(productId);
    set.add(productId);
    globalThis.__mayabuWishlist.set(user.id, set);
    return json(
      response,
      200,
      { status: existed ? "exists" : "added", count: set.size },
      requestId,
    );
  }
  if (url.pathname.startsWith("/api/wishlist/") && request.method === "DELETE") {
    const session = cookies.mayabu_session;
    const user = session ? globalThis.__mayabuUsers?.get(session) : null;
    if (!user) return json(response, 401, { detail: "Authentication required" }, requestId);
    const productId = url.pathname.split("/").pop();
    const set = globalThis.__mayabuWishlist.get(user.id) || new Set();
    const existed = set.delete(productId);
    globalThis.__mayabuWishlist.set(user.id, set);
    const watches = globalThis.__mayabuWatch?.get(user.id);
    watches?.delete(productId);
    return json(
      response,
      200,
      { status: existed ? "removed" : "absent", count: set.size },
      requestId,
    );
  }
  if (url.pathname === "/api/wishlist/status") {
    const session = cookies.mayabu_session;
    const user = session ? globalThis.__mayabuUsers?.get(session) : null;
    if (!user) return json(response, 401, { detail: "Authentication required" }, requestId);
    const ids = (url.searchParams.get("ids") || "").split(",").filter(Boolean);
    const set = globalThis.__mayabuWishlist.get(user.id) || new Set();
    const status = Object.fromEntries(ids.map((id) => [id, set.has(id)]));
    return json(response, 200, { status, count: set.size }, requestId);
  }

  return json(response, 404, { detail: "Not found" }, requestId);
});

server.listen(port, "127.0.0.1", () => console.log(`Mayabu mock API listening on ${port}`));

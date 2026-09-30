import { z } from "zod";

const nullableNumber = z.number().finite().nullable().optional();
const nullableString = z.string().nullable().optional();

export const productSpecsSchema = z
  .object({
    family: z.string().optional(),
    model_codes: z.array(z.string()).optional(),
    cpu_series: z.string().optional(),
    cpu_models: z.array(z.string()).optional(),
    gpu: z.string().optional(),
    ram_gb: z.number().finite().positive().optional(),
    storage_gb: z.number().finite().positive().optional(),
    screen_inch: z.number().finite().positive().optional(),
    // Retailer/spec sources sometimes emit generation as a number (e.g. 2).
    generation: z.union([z.string(), z.number()]).optional(),
  })
  .passthrough()
  .default({});

export const relationshipSchema = z.enum(["exact_match", "similar_variant", "related_product"]);

export const productSchema = z.object({
  id: z.string().min(1),
  title: z.string().default(""),
  brand: nullableString,
  category: nullableString,
  specs: productSpecsSchema,
  display_specs: z.record(z.string(), z.unknown()).optional(),
  family: nullableString,
  model_codes: z.array(z.string()).optional(),
  best_price: nullableNumber,
  best_platform: nullableString,
  platform_count: z.number().int().nonnegative().default(0),
  offer_count: z.number().int().nonnegative().optional(),
  image_url: nullableString,
  last_seen_at: nullableString,
  match_group: relationshipSchema.optional().default("related_product"),
  rank_score: nullableNumber,
  variant_group_id: nullableString,
  /** Optional consumer-safe conflict hints when the API exposes them. */
  hard_conflicts: z.array(z.string()).optional(),
  match_warning: nullableString,
});

const sectionsSchema = z.object({
  exact_matches: z.array(productSchema).default([]),
  similar_variants: z.array(productSchema).default([]),
  related_products: z.array(productSchema).default([]),
});

export const searchResponseSchema = z.object({
  query: z.string(),
  normalized_query: z.string().optional().default(""),
  intent: z.string().optional().default("search"),
  detected_category: nullableString,
  detected_brand: nullableString,
  detected_specs: z.record(z.string(), z.unknown()).optional().default({}),
  search_mode: z.string().optional(),
  category_confidence: z.string().optional(),
  min_price: nullableNumber,
  max_price: nullableNumber,
  public_categories: z.array(z.string()).optional().default([]),
  search_contract_version: z.string().optional(),
  result_count: z.number().int().nonnegative().default(0),
  limit: z.number().int().positive().default(20),
  offset: z.number().int().nonnegative().default(0),
  has_more: z.boolean().default(false),
  next_cursor: nullableString,
  results: z.array(productSchema).default([]),
  sections: sectionsSchema,
  exact_match_count: z.number().int().nonnegative().optional().default(0),
  similar_variant_count: z.number().int().nonnegative().optional().default(0),
  related_product_count: z.number().int().nonnegative().optional().default(0),
  facets: z
    .record(z.string(), z.array(z.object({ value: z.string(), count: z.number().int() })))
    .optional()
    .default({}),
  facet_scope: z.string().optional(),
  category_counts: z.record(z.string(), z.number().int()).optional().default({}),
  sort: z.string().optional(),
  message: nullableString,
});

export const offerSchema = z.object({
  id: z.string().min(1),
  platform: nullableString,
  listing_id: nullableString,
  native_id: nullableString,
  url: nullableString,
  title: z.string().default(""),
  image_url: nullableString,
  price: nullableNumber,
  mrp: nullableNumber,
  effective_price: nullableNumber,
  discount_percent: nullableNumber,
  currency: z.string().nullable().optional().default("INR"),
  stock_status: nullableString,
  rating: nullableNumber,
  review_count: z.number().int().nonnegative().nullable().optional(),
  last_checked_at: nullableString,
  last_verified_at: nullableString,
  verification_status: nullableString,
  verification_source: nullableString,
  next_allowed_verification_at: nullableString,
  verification_failures: z.number().int().nonnegative().default(0),
});

export const productDetailSchema = z.object({
  product: productSchema,
  offers: z.array(offerSchema).default([]),
  offer_count: z.number().int().nonnegative().default(0),
  similar_variants: z.array(productSchema).default([]),
  similar_variant_count: z.number().int().nonnegative().default(0),
  similar_products: z.array(productSchema).default([]),
  similar_product_count: z.number().int().nonnegative().default(0),
  images: z
    .array(
      z.object({
        url: z.string(),
        is_primary: z.boolean().optional(),
        source: nullableString.optional(),
      }),
    )
    .optional()
    .default([]),
  image_count: z.number().int().nonnegative().optional(),
});

export const offersResponseSchema = z.object({
  product_id: z.string(),
  offers: z.array(offerSchema).default([]),
  offer_count: z.number().int().nonnegative().default(0),
});

export const pricePointSchema = z
  .object({
    date: z.string().optional(),
    observed_at: z.string().optional(),
    amazon_price: nullableNumber,
    flipkart_price: nullableNumber,
    croma_price: nullableNumber,
    reliancedigital_price: nullableNumber,
    best_price: nullableNumber,
    best_platform: nullableString,
    platform_count: nullableNumber,
    observations_count: nullableNumber,
    all_time_low_so_far: nullableNumber,
  })
  .passthrough();

export const priceHistorySchema = z.object({
  product_id: z.string(),
  days: z.number().int().positive(),
  window: z.string().optional(),
  history: z.array(pricePointSchema).default([]),
  best_price: z
    .array(
      z.object({
        date: z.string(),
        price: z.number().finite(),
        observed: z.boolean().optional(),
      }),
    )
    .optional()
    .default([]),
  platforms: z
    .record(
      z.string(),
      z.array(
        z.object({
          date: z.string(),
          price: z.number().finite(),
          observed: z.boolean().optional(),
        }),
      ),
    )
    .optional()
    .default({}),
  missing_days_are_unobserved: z.boolean().optional(),
});

export const priceIntelligenceSchema = z.object({
  product_id: z.string(),
  current: z
    .object({
      price: nullableNumber,
      platform: nullableString,
      purchasability: z.string().optional(),
    })
    .passthrough(),
  freshness: z
    .object({
      hours: nullableNumber,
    })
    .passthrough(),
  store_coverage: z
    .object({
      store_count: z.number().int().nonnegative().optional(),
      in_stock_count: z.number().int().nonnegative().optional(),
    })
    .passthrough(),
  history_summary: z
    .object({
      observation_count: z.number().int().nonnegative().optional(),
      tracking_days: z.number().int().nonnegative().optional(),
      tracked_low: nullableNumber,
      tracked_high: nullableNumber,
    })
    .passthrough(),
  windows: z.record(z.string(), z.unknown()).optional().default({}),
  timing_signal: z
    .object({
      state: z.string(),
      label: z.string().optional(),
      reasons: z.array(z.string()).optional().default([]),
      reason_codes: z.array(z.string()).optional().default([]),
      window: z.string().optional(),
      freshness_hours: nullableNumber,
      store_count: z.number().int().nonnegative().optional(),
      in_stock_count: z.number().int().nonnegative().optional(),
      purchasability: z.string().optional(),
    })
    .passthrough(),
  reasons: z.array(z.string()).optional().default([]),
  reason_codes: z.array(z.string()).optional().default([]),
  signal: z.string().optional(),
  explanation: z.string().nullable().optional(),
  current_price: nullableNumber,
  retailer: nullableString,
  purchasability: z.string().optional(),
  movement: z
    .object({
      absolute: nullableNumber,
      percent: nullableNumber,
      previous_price: nullableNumber,
    })
    .passthrough()
    .optional(),
  platform_summary: z.record(z.string(), z.unknown()).optional().default({}),
  disclosure: z.string().optional(),
});

export const verificationRequestSchema = z.object({
  status: z.enum(["queued", "joined", "fresh", "cooldown", "busy", "no_offers"]),
  product_id: z.string(),
  mode: z.enum(["best_offer", "all_offers"]).optional(),
  task_ids: z.array(z.string()).default([]),
  tasks: z
    .array(
      z.object({
        task_id: z.string(),
        listing_id: z.string(),
        platform: nullableString,
        created: z.boolean(),
      }),
    )
    .optional()
    .default([]),
  skipped: z.array(z.record(z.string(), z.unknown())).optional().default([]),
  estimated_seconds: z.number().nonnegative().optional(),
  retry_after_seconds: z.number().nonnegative().optional(),
  message: z.string().optional(),
  coalesced: z.boolean().optional().default(false),
});

export const verificationJobStatusSchema = z.enum([
  "pending",
  "queued",
  "running",
  "completed",
  "failed",
  "dead",
  "cancelled",
  "paused",
]);

export const verificationJobSchema = z
  .object({
    task_id: z.string(),
    status: verificationJobStatusSchema,
    platform: nullableString,
    attempts: z.number().int().nonnegative().default(0),
    request_count: z.number().int().positive().default(1),
    result: z.record(z.string(), z.unknown()).default({}),
    last_error: nullableString,
    error_category: nullableString,
    created_at: nullableString,
    updated_at: nullableString,
    started_at: nullableString,
    completed_at: nullableString,
  })
  .passthrough();

export const verificationStatusSchema = z.record(z.string(), z.unknown());

export const homepageProductSchema = productSchema.extend({
  previous_price: nullableNumber,
  drop_amount: nullableNumber,
  drop_percent: nullableNumber,
  drop_window_days: z.number().int().positive().optional(),
  mrp: nullableNumber,
  discount_percent: nullableNumber,
  discount_amount: nullableNumber,
  tracked_low_price: nullableNumber,
  is_lowest_since_tracking: z.boolean().optional(),
  near_tracked_low: z.boolean().optional(),
  near_low_gap_percent: nullableNumber,
  tracking_observation_count: z.number().int().nonnegative().optional(),
  tracking_day_count: z.number().int().nonnegative().optional(),
  activity_badge: nullableString,
});

export const homepageDiscoverySchema = z.object({
  trending: z.array(homepageProductSchema).default([]),
  popular: z.array(homepageProductSchema).default([]),
  biggest_discounts: z.array(homepageProductSchema).default([]),
  lowest_since_tracking: z.array(homepageProductSchema).default([]),
  near_tracked_low: z.array(homepageProductSchema).default([]),
  price_drops: z.array(homepageProductSchema).default([]),
  recently_checked: z.array(homepageProductSchema).default([]),
  multi_store: z.array(homepageProductSchema).default([]),
  explore_by_category: z
    .array(
      z.object({
        slug: z.string(),
        label: z.string(),
        product_count: z.number().int().nonnegative().optional(),
        products: z.array(homepageProductSchema).default([]),
      }),
    )
    .default([]),
  category_spotlights: z
    .array(
      z.object({
        slug: z.string(),
        title: z.string(),
        description: z.string().optional(),
        products: z.array(homepageProductSchema).default([]),
      }),
    )
    .default([]),
  featured: z.array(homepageProductSchema).default([]),
  categories: z.array(z.string()).default([]),
  stores: z.array(z.unknown()).optional().default([]),
  semantics: z
    .object({
      trending: z.string().nullable().optional(),
      trending_note: z.string().nullable().optional(),
      popular: z.string().nullable().optional(),
      biggest_discounts: z.string().optional(),
      lowest_since_tracking: z.string().optional(),
      near_tracked_low: z.string().optional(),
      price_drops: z.string().optional(),
      recently_checked: z.string().optional(),
      multi_store: z.string().optional(),
      explore_by_category: z.string().optional(),
      category_spotlights: z.string().optional(),
      most_wishlisted: z.string().nullable().optional(),
      most_wishlisted_note: z.string().optional(),
    })
    .passthrough()
    .optional()
    .default({}),
});

export type Product = z.infer<typeof productSchema>;
export type Offer = z.infer<typeof offerSchema>;
export type SearchResponse = z.infer<typeof searchResponseSchema>;
export type ProductDetail = z.infer<typeof productDetailSchema>;
export type PricePoint = z.infer<typeof pricePointSchema>;
export type PriceHistory = z.infer<typeof priceHistorySchema>;
export type PriceIntelligence = z.infer<typeof priceIntelligenceSchema>;
export type VerificationRequest = z.infer<typeof verificationRequestSchema>;
export type VerificationJob = z.infer<typeof verificationJobSchema>;
export type Relationship = z.infer<typeof relationshipSchema>;
export type HomepageProduct = z.infer<typeof homepageProductSchema>;
export type HomepageDiscovery = z.infer<typeof homepageDiscoverySchema>;

export const searchSuggestProductSchema = z.object({
  id: z.string().min(1),
  title: z.string().default(""),
  brand: nullableString,
  category: nullableString,
  image_url: nullableString,
  best_price: nullableNumber,
  best_platform: nullableString,
  platform_count: z.number().int().nonnegative().optional().default(0),
  offer_count: z.number().int().nonnegative().optional().default(0),
  display_specs: z.record(z.string(), z.unknown()).optional().default({}),
  specs: productSpecsSchema.optional().default({}),
  model_codes: z.array(z.string()).optional().default([]),
});

export const searchSuggestSchema = z.object({
  query: z.string().default(""),
  products: z.array(searchSuggestProductSchema).default([]),
  categories: z
    .array(z.object({ slug: z.string(), label: z.string() }))
    .default([]),
  popular_queries: z
    .array(z.object({ query: z.string(), hits: z.number().int().nonnegative().optional() }))
    .default([]),
  search_contract_version: z.string().optional(),
});

export type SearchSuggestResponse = z.infer<typeof searchSuggestSchema>;

export const categoryLandingSchema = z.object({
  category: z.string(),
  display_name: z.string().optional(),
  product_count: z.number().int().nonnegative().optional(),
  product_count_sample: z.number().int().nonnegative().optional(),
  featured: z.array(homepageProductSchema).default([]),
  products: z.array(homepageProductSchema).default([]),
  facets: z
    .record(
      z.string(),
      z.array(
        z.object({
          value: z.union([z.string(), z.number(), z.boolean()]).transform(String),
          count: z.number().int().nonnegative(),
        }),
      ),
    )
    .default({}),
  facet_keys: z.array(z.string()).optional().default([]),
  price_drops: z.array(homepageProductSchema).default([]),
  biggest_discounts: z.array(homepageProductSchema).default([]),
  lowest_since_tracking: z.array(homepageProductSchema).default([]),
  trending: z.array(homepageProductSchema).default([]),
  popular: z.array(homepageProductSchema).default([]),
  related_categories: z.array(z.string()).default([]),
  semantics: z.record(z.string(), z.unknown()).optional().default({}),
  contract_version: z.string().optional(),
  search_contract_version: z.string().optional(),
});

export type CategoryLandingPayload = z.infer<typeof categoryLandingSchema>;

export const compareResponseSchema = z.object({
  products: z.array(productSchema).default([]),
  category: nullableString,
  requested_ids: z.array(z.string()).default([]),
  missing_ids: z.array(z.string()).default([]),
  skipped: z
    .array(
      z.object({
        id: z.string(),
        reason: z.string(),
        category: nullableString.optional(),
      }),
    )
    .default([]),
  warnings: z.array(z.string()).default([]),
});

export type CompareResponse = z.infer<typeof compareResponseSchema>;

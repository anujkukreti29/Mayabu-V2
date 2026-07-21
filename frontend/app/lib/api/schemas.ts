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
    generation: z.string().optional(),
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
  best_price: nullableNumber,
  best_platform: nullableString,
  platform_count: z.number().int().nonnegative().default(0),
  offer_count: z.number().int().nonnegative().optional(),
  image_url: nullableString,
  last_seen_at: nullableString,
  match_group: relationshipSchema.optional().default("related_product"),
  rank_score: nullableNumber,
  variant_group_id: nullableString,
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
  history: z.array(pricePointSchema).default([]),
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

export type Product = z.infer<typeof productSchema>;
export type Offer = z.infer<typeof offerSchema>;
export type SearchResponse = z.infer<typeof searchResponseSchema>;
export type ProductDetail = z.infer<typeof productDetailSchema>;
export type PricePoint = z.infer<typeof pricePointSchema>;
export type PriceHistory = z.infer<typeof priceHistorySchema>;
export type VerificationRequest = z.infer<typeof verificationRequestSchema>;
export type VerificationJob = z.infer<typeof verificationJobSchema>;
export type Relationship = z.infer<typeof relationshipSchema>;

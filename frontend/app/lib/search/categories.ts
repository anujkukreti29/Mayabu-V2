/** Centralized public category display names for search UI. */

export const PUBLIC_CATEGORY_SLUGS = [
  "laptop",
  "smartphone",
  "television",
  "refrigerator",
  "washing_machine",
  "tws",
  "headphones",
  "camera",
] as const;

export type PublicCategorySlug = (typeof PUBLIC_CATEGORY_SLUGS)[number];

const CATEGORY_DISPLAY: Record<string, string> = {
  laptop: "Laptops",
  smartphone: "Smartphones",
  television: "TVs",
  refrigerator: "Refrigerators",
  washing_machine: "Washing Machines",
  tws: "TWS & Earbuds",
  headphones: "Headphones",
  camera: "Cameras",
};

const CATEGORY_SHORT: Record<string, string> = {
  laptop: "Laptop",
  smartphone: "Smartphone",
  television: "TV",
  refrigerator: "Refrigerator",
  washing_machine: "Washer",
  tws: "Earbuds",
  headphones: "Headphones",
  camera: "Camera",
};

export function categoryDisplayName(slug: string | null | undefined): string {
  if (!slug) return "";
  return CATEGORY_DISPLAY[slug] ?? slug;
}

export function categoryShortLabel(slug: string | null | undefined): string {
  if (!slug) return "";
  return CATEGORY_SHORT[slug] ?? categoryDisplayName(slug);
}

export function isPublicCategory(slug: string | null | undefined): slug is PublicCategorySlug {
  return Boolean(slug && (PUBLIC_CATEGORY_SLUGS as readonly string[]).includes(slug));
}

/** Prefer backend public_categories; fall back to known public list. */
export function resolvePublicCategories(fromApi?: string[] | null): string[] {
  const filtered = (fromApi ?? []).filter((slug) => isPublicCategory(slug));
  return filtered.length > 0 ? filtered : [...PUBLIC_CATEGORY_SLUGS];
}

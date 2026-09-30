import { CATEGORY_ROUTE_BY_SLUG } from "~/lib/category/landing-registry";
import { categoryDisplayName } from "~/lib/search/categories";

export type CategoryStatus = "available" | "coming_soon";

export type HomeCategoryIcon =
  | "laptop"
  | "smartphone"
  | "earbuds"
  | "headphones"
  | "tv"
  | "camera"
  | "washer"
  | "fridge";

export interface HomeCategory {
  id: string;
  label: string;
  status: CategoryStatus;
  icon: HomeCategoryIcon;
  href: string;
  slug: string;
}

export const homeHero = {
  eyebrow: "Compare smarter across stores",
  title: "Compare prices. Track drops. Know when to buy.",
  description:
    "Mayabu matches equivalent products across supported Indian stores—phones, TVs, appliances, audio, and more—with freshness and price evidence.",
  searchPlaceholder: "Search phones, TVs, appliances, earbuds…",
  searchAvailability: "Live price checks · Multi-store comparison · Observed price history",
} as const;

/** Live public categories only — used by navbar mega-menu and carousel mosaic. */
export const homeCategories: readonly HomeCategory[] = [
  {
    id: "laptops",
    label: categoryDisplayName("laptop"),
    status: "available",
    icon: "laptop",
    href: CATEGORY_ROUTE_BY_SLUG.laptop,
    slug: "laptop",
  },
  {
    id: "smartphones",
    label: categoryDisplayName("smartphone"),
    status: "available",
    icon: "smartphone",
    href: CATEGORY_ROUTE_BY_SLUG.smartphone,
    slug: "smartphone",
  },
  {
    id: "tvs",
    label: categoryDisplayName("television"),
    status: "available",
    icon: "tv",
    href: CATEGORY_ROUTE_BY_SLUG.television,
    slug: "television",
  },
  {
    id: "refrigerators",
    label: categoryDisplayName("refrigerator"),
    status: "available",
    icon: "fridge",
    href: CATEGORY_ROUTE_BY_SLUG.refrigerator,
    slug: "refrigerator",
  },
  {
    id: "washing-machines",
    label: categoryDisplayName("washing_machine"),
    status: "available",
    icon: "washer",
    href: CATEGORY_ROUTE_BY_SLUG.washing_machine,
    slug: "washing_machine",
  },
  {
    id: "tws",
    label: categoryDisplayName("tws"),
    status: "available",
    icon: "earbuds",
    href: CATEGORY_ROUTE_BY_SLUG.tws,
    slug: "tws",
  },
  {
    id: "headphones",
    label: categoryDisplayName("headphones"),
    status: "available",
    icon: "headphones",
    href: CATEGORY_ROUTE_BY_SLUG.headphones,
    slug: "headphones",
  },
  {
    id: "cameras",
    label: categoryDisplayName("camera"),
    status: "available",
    icon: "camera",
    href: CATEGORY_ROUTE_BY_SLUG.camera,
    slug: "camera",
  },
];

/** Category landing registry and route map. */

import { describe, expect, it } from "vitest";
import {
  CATEGORY_ROUTE_BY_SLUG,
  allCategoryLandingConfigs,
  categoryLandingPath,
  categorySlugFromPath,
  getCategoryLandingConfig,
} from "~/lib/category/landing-registry";
import { PUBLIC_CATEGORY_SLUGS } from "~/lib/search/categories";

describe("category landing registry", () => {
  it("maps all eight public categories to plural landing routes", () => {
    expect(Object.keys(CATEGORY_ROUTE_BY_SLUG).sort()).toEqual([...PUBLIC_CATEGORY_SLUGS].sort());
    expect(categoryLandingPath("laptop")).toBe("/laptops");
    expect(categoryLandingPath("smartphone")).toBe("/smartphones");
    expect(categoryLandingPath("washing_machine")).toBe("/washing-machines");
    expect(categoryLandingPath("camera")).toBe("/cameras");
    expect(categorySlugFromPath("/smartphones")).toBe("smartphone");
    expect(categorySlugFromPath("/washing-machines")).toBe("washing_machine");
  });

  it("exposes discovery copy and primary facets per category", () => {
    const laptop = getCategoryLandingConfig("laptop");
    expect(laptop.primaryFacets).toContain("ram_gb");
    expect(laptop.searchPlaceholder.toLowerCase()).toContain("laptop");
    expect(getCategoryLandingConfig("camera").primaryFacets).toContain("body_only");
    expect(allCategoryLandingConfigs()).toHaveLength(8);
  });
});

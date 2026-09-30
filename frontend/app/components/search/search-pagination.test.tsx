import { describe, expect, it } from "vitest";
import {
  nextSearchOffset,
  previousSearchOffset,
  searchPaginationHref,
} from "~/components/search/search-pagination";
import type { SearchUrlState } from "~/lib/search/url";

const base: SearchUrlState = {
  q: "gaming laptop",
  category: null,
  sort: "relevance",
  filters: {},
  offset: 0,
};

describe("search pagination helpers", () => {
  it("builds shareable offset URLs and preserves filters", () => {
    expect(searchPaginationHref(base, 0)).toBe("/search?q=gaming+laptop");
    expect(searchPaginationHref(base, 20)).toBe("/search?q=gaming+laptop&offset=20");
    expect(
      searchPaginationHref(
        { ...base, category: "laptop", sort: "price_asc", filters: { ram_gb: 16 } },
        20,
      ),
    ).toBe(
      "/search?q=gaming+laptop&category=laptop&sort=price_asc&filters=%7B%22ram_gb%22%3A16%7D&offset=20",
    );
  });

  it("advances and retreats by page size", () => {
    expect(nextSearchOffset(0, 20)).toBe(20);
    expect(previousSearchOffset(20, 20)).toBe(0);
    expect(previousSearchOffset(0, 20)).toBe(0);
  });
});

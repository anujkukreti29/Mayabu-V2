import { describe, expect, it, beforeEach, afterEach } from "vitest";
import {
  clearRecentSearches,
  pushRecentSearch,
  readRecentSearches,
  removeRecentSearch,
} from "~/lib/search/recent-searches";

describe("recent searches", () => {
  beforeEach(() => {
    clearRecentSearches();
  });

  afterEach(() => {
    clearRecentSearches();
  });

  it("stores bounded unique queries newest-first", () => {
    for (let i = 0; i < 12; i += 1) {
      pushRecentSearch(`query-${i}`);
    }
    const recent = readRecentSearches();
    expect(recent).toHaveLength(8);
    expect(recent[0]).toBe("query-11");
    expect(recent).not.toContain("query-0");
  });

  it("dedupes case-insensitively and moves to front", () => {
    pushRecentSearch("iphone");
    pushRecentSearch("galaxy");
    pushRecentSearch("IPHONE");
    expect(readRecentSearches()).toEqual(["IPHONE", "galaxy"]);
  });

  it("ignores short queries", () => {
    pushRecentSearch("a");
    expect(readRecentSearches()).toEqual([]);
  });

  it("removes a single entry", () => {
    pushRecentSearch("iphone");
    pushRecentSearch("galaxy");
    expect(removeRecentSearch("iphone")).toEqual(["galaxy"]);
  });
});

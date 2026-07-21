import { describe, expect, it } from "vitest";
import { productKeys, searchKeys, verificationKeys } from "~/lib/query/keys";

describe("query key factories", () => {
  it("keeps product caches scoped", () =>
    expect(productKeys.detail("p1")).toEqual(["product", "p1"]));
  it("isolates verification jobs", () =>
    expect(verificationKeys.job("t1")).toEqual(["verification", "job", "t1"]));
  it("retains search parameters", () =>
    expect(searchKeys.results({ q: "laptop" })).toEqual(["search", { q: "laptop" }]));
});

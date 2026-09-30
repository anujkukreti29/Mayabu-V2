import { describe, expect, it } from "vitest";
import { safeNextPath } from "~/lib/auth/safe-next";

describe("safeNextPath", () => {
  it("allows safe relative paths", () => {
    expect(safeNextPath("/wishlist")).toBe("/wishlist");
    expect(safeNextPath("/account?tab=1")).toBe("/account?tab=1");
  });

  it("rejects open redirects", () => {
    expect(safeNextPath("https://evil.example/")).toBe("/account");
    expect(safeNextPath("//evil.example")).toBe("/account");
    expect(safeNextPath("/\\evil")).toBe("/account");
  });
});

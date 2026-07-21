import { afterEach, describe, expect, it, vi } from "vitest";
import { formatRelativeTime, freshnessFrom } from "~/lib/formatting/freshness";

describe("freshness labels", () => {
  afterEach(() => vi.useRealTimers());

  it("labels recent checks without claiming guaranteed live data", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-18T12:00:00Z"));
    expect(freshnessFrom("2026-07-18T11:55:00Z")).toEqual({
      label: "Verified recently",
      tone: "success",
    });
  });

  it("uses a compact native relative-time formatter", () => {
    const now = Date.parse("2026-07-18T12:00:00Z");
    expect(formatRelativeTime("2026-07-18T10:00:00Z", now)).toBe("2 hours ago");
    expect(formatRelativeTime("2026-07-21T12:00:00Z", now)).toBe("in 3 days");
  });

  it("labels old records as last known prices", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-18T12:00:00Z"));
    expect(freshnessFrom("2026-07-15T12:00:00Z")).toEqual({
      label: "Last known price · 3 days ago",
      tone: "warning",
    });
  });

  it("handles missing and invalid timestamps", () => {
    expect(freshnessFrom(null).label).toBe("Verification unavailable");
    expect(freshnessFrom("not-a-date").label).toBe("Verification unavailable");
    expect(formatRelativeTime("not-a-date")).toBeNull();
  });
});

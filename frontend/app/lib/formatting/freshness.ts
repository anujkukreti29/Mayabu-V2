export type FreshnessTone = "success" | "warning" | "neutral";

type RelativeUnit = "second" | "minute" | "hour" | "day" | "month" | "year";

const relativeFormatter = new Intl.RelativeTimeFormat("en", {
  numeric: "always",
  style: "long",
});

const units: ReadonlyArray<[RelativeUnit, number]> = [
  ["year", 365 * 24 * 60 * 60],
  ["month", 30 * 24 * 60 * 60],
  ["day", 24 * 60 * 60],
  ["hour", 60 * 60],
  ["minute", 60],
  ["second", 1],
];

export function formatRelativeTime(value: string, now = Date.now()): string | null {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return null;

  const deltaSeconds = (timestamp - now) / 1_000;
  const absoluteSeconds = Math.abs(deltaSeconds);
  const [unit, unitSeconds] =
    units.find(([, seconds]) => absoluteSeconds >= seconds) ?? (["second", 1] as const);
  return relativeFormatter.format(Math.round(deltaSeconds / unitSeconds), unit);
}

export function freshnessFrom(value: string | null | undefined): {
  label: string;
  tone: FreshnessTone;
} {
  if (!value) return { label: "Verification unavailable", tone: "neutral" };
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    return { label: "Verification unavailable", tone: "neutral" };
  }

  const ageMinutes = Math.max(0, (Date.now() - timestamp) / 60_000);
  const distance = formatRelativeTime(value);
  if (!distance) return { label: "Verification unavailable", tone: "neutral" };
  if (ageMinutes <= 15) return { label: "Verified recently", tone: "success" };
  if (ageMinutes <= 24 * 60) return { label: `Last checked ${distance}`, tone: "success" };
  return { label: `Last known price · ${distance}`, tone: "warning" };
}

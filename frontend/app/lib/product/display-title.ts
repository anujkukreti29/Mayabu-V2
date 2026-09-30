/**
 * Compact display titles for dense surfaces (carousel tiles, rails, cards).
 * Canonical DB titles remain unchanged — this is presentation only.
 */

export interface DisplayTitleParts {
  title: string;
  subtitle: string | null;
}

function cleanSpaces(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function firstMatch(text: string, patterns: RegExp[]): string | null {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match?.[1]) return cleanSpaces(match[1]);
  }
  return null;
}

function memoryLine(text: string): string | null {
  const ram = firstMatch(text, [/(\d+\s*GB)\s*RAM/i, /(\d+\s*GB)\s*\/\s*\d+\s*GB/i]);
  const storage = firstMatch(text, [
    /(\d+\s*(?:GB|TB))\s*(?:SSD|HDD|storage|eMMC)/i,
    /\d+\s*GB\s*\/\s*(\d+\s*(?:GB|TB))/i,
  ]);
  const parts = [ram, storage].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function tvLine(text: string): string | null {
  const size = firstMatch(text, [/(\d{2,3})\s*(?:cm|"|inch|inches)/i]);
  const panel = firstMatch(text, [/\b(OLED|QLED|Neo QLED|Mini[- ]?LED|LED)\b/i]);
  const res = firstMatch(text, [/\b(8K|4K|UHD|Full HD|FHD|HD)\b/i]);
  const parts = [
    size ? (/\d+\s*cm/i.test(size) ? size : `${size}"`) : null,
    panel,
    res,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function audioLine(text: string): string | null {
  const bits: string[] = [];
  for (const pattern of [/\bANC\b/i, /\bWireless\b/i, /\bBluetooth\b/i, /\bTWS\b/i]) {
    const match = text.match(pattern);
    if (match?.[0] && !bits.includes(match[0])) bits.push(match[0]);
  }
  return bits.length > 0 ? bits.slice(0, 3).join(" · ") : null;
}

function shortenRawTitle(title: string, max = 52): string {
  const cleaned = cleanSpaces(
    title
      .replace(/\s*\([^)]{0,80}\)\s*/g, " ")
      .replace(/\s*\[[^\]]{0,80}\]\s*/g, " ")
      .replace(/\s{2,}/g, " "),
  );
  if (cleaned.length <= max) return cleaned;
  const cut = cleaned.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > 28 ? cut.slice(0, lastSpace) : cut).trim()}…`;
}

export function buildDisplayTitle(input: {
  title?: string | null;
  brand?: string | null;
  category?: string | null;
  specs?: Record<string, unknown> | null;
}): DisplayTitleParts {
  const raw = cleanSpaces(input.title || "");
  if (!raw) {
    return { title: "Untitled product", subtitle: null };
  }

  const brand = cleanSpaces(input.brand || "");
  const category = (input.category || "").toLowerCase();
  const specs = input.specs || {};

  const specBits: string[] = [];
  const pushSpec = (value: unknown) => {
    if (value == null || value === "") return;
    if (typeof value !== "string" && typeof value !== "number" && typeof value !== "boolean") {
      return;
    }
    const text = cleanSpaces(String(value));
    if (text && !specBits.includes(text)) specBits.push(text);
  };

  if (category.includes("laptop") || category.includes("smartphone") || category.includes("phone")) {
    pushSpec(specs.ram || specs.memory);
    pushSpec(specs.storage || specs.internal_storage);
  }
  if (category.includes("television") || category.includes("tv")) {
    pushSpec(specs.screen_size || specs.size);
    pushSpec(specs.panel_type || specs.display_type);
    pushSpec(specs.resolution);
  }
  if (category.includes("tws") || category.includes("headphone") || category.includes("audio")) {
    pushSpec(specs.type);
    pushSpec(specs.connectivity);
    if (specs.anc || specs.noise_cancellation) pushSpec("ANC");
  }
  if (category.includes("camera")) {
    pushSpec(specs.kit || specs.lens);
    pushSpec(specs.sensor);
  }
  if (category.includes("refrigerator") || category.includes("washing")) {
    pushSpec(specs.capacity);
    pushSpec(specs.type || specs.load_type);
  }

  let subtitle = specBits.slice(0, 3).join(" · ") || null;
  if (!subtitle) {
    if (category.includes("tv") || category.includes("television")) subtitle = tvLine(raw);
    else if (category.includes("tws") || category.includes("headphone")) subtitle = audioLine(raw);
    else subtitle = memoryLine(raw);
  }

  let title = shortenRawTitle(raw);
  if (brand && raw.toLowerCase().startsWith(brand.toLowerCase())) {
    const rest = cleanSpaces(raw.slice(brand.length));
    const model = shortenRawTitle(rest || raw, 40);
    title = model.toLowerCase().startsWith(brand.toLowerCase())
      ? model
      : cleanSpaces(`${brand} ${model}`);
  }

  return { title, subtitle };
}

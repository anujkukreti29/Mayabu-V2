/** Presentation-only spec formatting. Never mutates canonical stored values. */

import type { Product } from "~/lib/api/schemas";
import { categoryDisplayName } from "~/lib/search/categories";

const PROCESSOR_FAMILIES: Array<[string, string]> = [
  ["intel_core_ultra", "Intel Core Ultra"],
  ["intel_core", "Intel Core"],
  ["intel_celeron", "Intel Celeron"],
  ["intel_pentium", "Intel Pentium"],
  ["intel_processor", "Intel Processor"],
  ["amd_ryzen_ai", "AMD Ryzen AI"],
  ["amd_ryzen", "AMD Ryzen"],
  ["amd_athlon", "AMD Athlon"],
  ["snapdragon", "Snapdragon"],
  ["mediatek_dimensity", "MediaTek Dimensity"],
  ["mediatek_helio", "MediaTek Helio"],
  ["apple_m", "Apple M"],
  ["apple_a", "Apple A"],
  ["exynos", "Exynos"],
  ["tensor", "Google Tensor"],
];

const ENUM_ALIASES: Record<string, string> = {
  body_only: "Body Only",
  body_kit: "Body + Kit",
  with_kit: "With kit",
  front_load: "Front Load",
  top_load: "Top Load",
  double_door: "Double Door",
  single_door: "Single Door",
  side_by_side: "Side by Side",
  french_door: "French Door",
  frost_free: "Frost Free",
  direct_cool: "Direct Cool",
  fully_automatic: "Fully Automatic",
  semi_automatic: "Semi Automatic",
  over_ear: "Over-ear",
  on_ear: "On-ear",
  in_ear: "In-ear",
  wireless: "Wireless",
  wired: "Wired",
  usb_c: "USB-C",
  oled: "OLED",
  qled: "QLED",
  mini_led: "Mini-LED",
  mini_led_panel: "Mini-LED",
};

const KNOWN_BRANDS: Record<string, string> = {
  lg: "LG",
  hp: "HP",
  asus: "ASUS",
  msi: "MSI",
  rca: "RCA",
  tcl: "TCL",
  jbl: "JBL",
};

const VARIANT_KEYS: Record<string, readonly string[]> = {
  laptop: ["ram_gb", "storage_gb"],
  smartphone: ["ram_gb", "storage_gb"],
  television: ["screen_size_inch", "panel_type", "resolution"],
  refrigerator: ["capacity_l", "door_type"],
  washing_machine: ["capacity_kg", "load_type"],
  camera: ["body_only", "kit_lens"],
  headphones: ["form_factor", "connectivity"],
  tws: ["anc", "generation"],
};

const MATCH_EVIDENCE_KEYS = [
  "model_codes",
  "ram_gb",
  "storage_gb",
  "screen_inch",
  "screen_size_inch",
  "capacity_l",
  "capacity_kg",
  "body_only",
  "kit_lens",
  "panel_type",
  "resolution",
  "load_type",
  "door_type",
  "cpu_series",
  "gpu",
  "generation",
  "connectivity",
  "form_factor",
  "network_generation",
] as const;

export function looksLikeInternalToken(value: string): boolean {
  const text = value.trim();
  if (!text) return false;
  if (/^(null|undefined|none|n\/a)$/i.test(text)) return true;
  if (/^[a-z0-9]+(_[a-z0-9]+)+\s*:/.test(text)) return true;
  if (/^[a-z][a-z0-9_]*:[a-z0-9_.:-]+$/i.test(text) && text.includes("_")) return true;
  return false;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) {
    return Number(value);
  }
  return null;
}

function alreadyHasUnit(text: string, unit: string): boolean {
  return new RegExp(`\\b${unit.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(text);
}

function titleCaseWords(text: string): string {
  return text
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      if (/^(OLED|QLED|LED|LCD|IPS|VA|HDR|UHD|FHD|HD|ANC|USB|GB|TB|MP|Hz)$/i.test(word)) {
        return word.toUpperCase();
      }
      if (word.length <= 2 && /[A-Z0-9]/.test(word)) return word.toUpperCase();
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

export function humanizeEnumValue(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  const alias = ENUM_ALIASES[trimmed.toLowerCase()];
  if (alias) return alias;

  const kit = trimmed.match(/^body[_-]?(\d+)[_-](\d+)\s*(mm)?$/i);
  if (kit) return `Body + ${kit[1]}–${kit[2]}mm Kit`;

  if (/^(oled|qled|led|lcd|ips|va|mini.?led|4k|8k|fhd|uhd|hd)$/i.test(trimmed.replace(/_/g, ""))) {
    return trimmed.replace(/_/g, " ").toUpperCase().replace("MINI LED", "MINI-LED");
  }

  return titleCaseWords(trimmed.replace(/_+/g, " "));
}

function formatModelToken(part: string): string {
  const token = part.trim();
  if (!token) return "";
  if (/^\d+[a-z]$/i.test(token)) return token.slice(0, -1) + token.slice(-1).toUpperCase();
  if (/^[a-z]\d/i.test(token) && token.length <= 6) return token.toUpperCase();
  return humanizeEnumValue(token).replace(/\bGen\b/i, "Gen");
}

export function formatProcessorValue(raw: string): string {
  const text = raw.trim();
  if (!text) return "";
  const parts = text.split(":").map((part) => part.trim()).filter(Boolean);
  const familyKey = (parts[0] || "").toLowerCase();
  const family = PROCESSOR_FAMILIES.find(([key]) => familyKey === key || familyKey.startsWith(`${key}_`));
  const familyLabel = family?.[1] ?? (familyKey.includes("_") ? humanizeEnumValue(familyKey) : "");
  if (!familyLabel && parts.length < 2) return humanizeEnumValue(text);
  const rest = parts.slice(1).map(formatModelToken).filter(Boolean);
  return [familyLabel || humanizeEnumValue(parts[0] || ""), ...rest].join(" ").replace(/\s+/g, " ").trim();
}

function formatBoolean(key: string, value: unknown): string | null {
  const truthy = value === true || value === "true" || value === "1" || value === 1 || value === "yes";
  const falsy = value === false || value === "false" || value === "0" || value === 0 || value === "no";
  if (!truthy && !falsy) return null;
  if (key === "body_only") return truthy ? "Body Only" : "With kit";
  if (key === "anc") return truthy ? "ANC" : "No ANC";
  return truthy ? "Yes" : "No";
}

function withUnit(num: number, unit: string): string {
  return `${num} ${unit}`;
}

function asText(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

export function formatSpecValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "string" && /^(null|undefined|none|n\/a)$/i.test(value.trim())) return "";

  if (Array.isArray(value)) {
    const joined = value
      .map((item) => formatSpecValue(key, item))
      .filter(Boolean)
      .join(", ");
    return joined;
  }

  const bool = formatBoolean(key, value);
  if (bool) return bool;

  const rawText = asText(value);
  const num = asNumber(value);
  if (num !== null && typeof value !== "boolean") {
    if (key === "ram_gb") return alreadyHasUnit(rawText, "GB") ? rawText.trim() : withUnit(num, "GB");
    if (key === "storage_gb") {
      if (alreadyHasUnit(rawText, "GB")) return rawText.trim();
      if (num >= 1000 && num % 1000 === 0) return withUnit(num / 1000, "TB");
      return withUnit(num, "GB");
    }
    if (key === "screen_inch" || key === "screen_size_inch") {
      if (rawText.includes('"')) return rawText.trim();
      return `${num}"`;
    }
    if (key === "capacity_l") return alreadyHasUnit(rawText, "L") ? rawText.trim() : withUnit(num, "L");
    if (key === "capacity_kg" || key === "weight_kg") {
      return alreadyHasUnit(rawText, "kg") ? rawText.trim() : withUnit(num, "kg");
    }
    if (key === "refresh_rate_hz") {
      return alreadyHasUnit(rawText, "Hz") ? rawText.trim() : withUnit(num, "Hz");
    }
    if (key === "rpm") return alreadyHasUnit(rawText, "RPM") ? rawText.trim() : withUnit(num, "RPM");
    if (key === "star_rating") return `${num}★`;
    if (key === "megapixels") return alreadyHasUnit(rawText, "MP") ? rawText.trim() : withUnit(num, "MP");
    if (key === "battery_wh") return withUnit(num, "Wh");
    if (key === "battery_mah") return withUnit(num, "mAh");
    if (key === "battery_hours") return withUnit(num, "h");
    if (key === "tonnage" || key === "capacity_ton") return withUnit(num, "ton");
  }

  const text = rawText.trim();
  if (!text) return "";

  if (key === "brand") {
    const known = KNOWN_BRANDS[text.toLowerCase()];
    if (known) return known;
    return text.replace(/\b\w/g, (c) => c.toUpperCase());
  }
  if (key === "category") {
    return categoryDisplayName(text) || humanizeEnumValue(text);
  }
  if (key === "cpu_series" || key === "cpu_models" || key === "chipset" || key === "processor") {
    return formatProcessorValue(text);
  }
  if (key === "kit_lens") {
    return humanizeEnumValue(text);
  }
  if (key === "gpu") {
    if (looksLikeInternalToken(text) || text.includes("_")) return humanizeEnumValue(text);
    return text;
  }

  if (
    key === "load_type" ||
    key === "door_type" ||
    key === "automation_type" ||
    key === "form_factor" ||
    key === "connectivity" ||
    key === "panel_type" ||
    key === "frost_type" ||
    key === "resolution" ||
    key === "display_type" ||
    key === "camera_type" ||
    key === "sensor_format"
  ) {
    return humanizeEnumValue(text);
  }

  if (looksLikeInternalToken(text) || (text.includes("_") && text === text.toLowerCase())) {
    if (text.includes(":")) return formatProcessorValue(text);
    return humanizeEnumValue(text);
  }

  return text;
}

function readProductSpec(product: Product, key: string): unknown {
  const display = product.display_specs;
  if (display && display[key] != null && display[key] !== "") return display[key];
  const specs = product.specs ?? {};
  if (specs[key] != null && specs[key] !== "") return specs[key];
  if (key === "model_codes") return product.model_codes?.[0];
  return undefined;
}

export function variantIdentityParts(product: Product): string[] {
  const keys = VARIANT_KEYS[(product.category || "").toLowerCase()] ?? [];
  const parts: string[] = [];
  for (const key of keys) {
    const formatted = formatSpecValue(key, readProductSpec(product, key));
    if (formatted) parts.push(formatted);
  }
  return parts;
}

export function variantIdentityLine(product: Product): string | null {
  const parts = variantIdentityParts(product);
  return parts.length > 0 ? parts.join(" · ") : null;
}

const MATCH_LABELS: Record<string, string> = {
  ram_gb: "RAM",
  storage_gb: "Storage",
  screen_inch: "Screen size",
  screen_size_inch: "Screen size",
  resolution: "Resolution",
  capacity_l: "Capacity",
  capacity_kg: "Capacity",
  door_type: "Door type",
  load_type: "Load type",
  body_only: "Kit type",
  kit_lens: "Kit lens",
  panel_type: "Panel",
  form_factor: "Form factor",
  connectivity: "Connectivity",
  anc: "ANC",
  generation: "Generation",
};

const SCORE_KEY = /(score|confidence|similarity|rank)/i;

export function matchEvidenceRows(
  product: Product,
): Array<{ key: string; label: string; value: string }> {
  const rows: Array<{ key: string; label: string; value: string }> = [];
  const model = product.model_codes?.[0];
  if (model && !SCORE_KEY.test(String(model))) {
    rows.push({ key: "model_codes", label: "Model", value: String(model) });
  }

  const categoryKeys = VARIANT_KEYS[(product.category || "").toLowerCase()] ?? [];
  const keys = [...new Set([...categoryKeys, ...MATCH_EVIDENCE_KEYS])];
  for (const key of keys) {
    if (key === "model_codes" || SCORE_KEY.test(key)) continue;
    const formatted = formatSpecValue(key, readProductSpec(product, key));
    if (!formatted || SCORE_KEY.test(formatted)) continue;
    rows.push({ key, label: MATCH_LABELS[key] ?? key, value: formatted });
  }
  return rows.slice(0, 6);
}

const CONFLICT_LABELS: Record<string, string> = {
  ram_gb: "RAM",
  storage_gb: "storage",
  gpu: "graphics",
  cpu_series: "processor",
  screen_inch: "screen size",
  screen_size_inch: "screen size",
  capacity_l: "capacity",
  capacity_kg: "capacity",
  body_only: "kit type",
  kit_lens: "kit lens",
  door_type: "door type",
  load_type: "load type",
};

/** Consumer-safe hard-conflict warning when the API exposes conflict fields. */
export function hardConflictWarning(product: Product): string | null {
  const direct = product.match_warning?.trim();
  if (direct && !SCORE_KEY.test(direct)) return direct;
  const conflicts = (product.hard_conflicts || [])
    .map((item) => String(item).trim())
    .filter((item) => item && !SCORE_KEY.test(item));
  if (conflicts.length === 0) return null;
  const labels = conflicts
    .map((item) => CONFLICT_LABELS[item] || item.replaceAll("_", " "))
    .slice(0, 3);
  return `Some listings may differ on ${labels.join(", ")}. Mayabu keeps conflicting configurations separate when evidence is unclear.`;
}

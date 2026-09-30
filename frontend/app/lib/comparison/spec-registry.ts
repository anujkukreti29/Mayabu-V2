import type { Product } from "~/lib/api/schemas";
import { formatFacetValue, facetLabel } from "~/lib/search/facets";
import type { PublicCategorySlug } from "~/lib/search/categories";
import { formatPrice, validPrice } from "~/lib/formatting/price";

export type CompareSpecImportance = "critical" | "high" | "normal";

/** Category-relevant row groups for compare navigation (plus synthetic Key differences / Price). */
export type CompareSpecGroup =
  | "Display"
  | "Performance"
  | "Storage"
  | "Camera"
  | "Battery"
  | "Audio"
  | "Connectivity"
  | "Design"
  | "Capacity"
  | "Features";

export type CompareSpecRowDef = {
  key: string;
  label: string;
  /** Spec keys to try in order (first present wins for formatting source). */
  sources: readonly string[];
  importance: CompareSpecImportance;
  group: CompareSpecGroup;
};

const LAPTOP_ROWS: CompareSpecRowDef[] = [
  {
    key: "processor",
    label: "Processor",
    sources: ["cpu_models", "cpu_series"],
    importance: "high",
    group: "Performance",
  },
  { key: "ram_gb", label: "RAM", sources: ["ram_gb"], importance: "critical", group: "Storage" },
  {
    key: "storage_gb",
    label: "Storage",
    sources: ["storage_gb"],
    importance: "critical",
    group: "Storage",
  },
  { key: "gpu", label: "Graphics", sources: ["gpu"], importance: "high", group: "Performance" },
  {
    key: "screen_inch",
    label: "Screen Size",
    sources: ["screen_inch"],
    importance: "high",
    group: "Display",
  },
  {
    key: "resolution",
    label: "Display",
    sources: ["resolution", "display_type"],
    importance: "normal",
    group: "Display",
  },
  {
    key: "refresh_rate_hz",
    label: "Refresh Rate",
    sources: ["refresh_rate_hz"],
    importance: "normal",
    group: "Display",
  },
  { key: "weight_kg", label: "Weight", sources: ["weight_kg"], importance: "normal", group: "Design" },
  {
    key: "battery",
    label: "Battery",
    sources: ["battery_wh", "battery_hours"],
    importance: "normal",
    group: "Battery",
  },
];

const SMARTPHONE_ROWS: CompareSpecRowDef[] = [
  { key: "ram_gb", label: "RAM", sources: ["ram_gb"], importance: "critical", group: "Storage" },
  {
    key: "storage_gb",
    label: "Storage",
    sources: ["storage_gb"],
    importance: "critical",
    group: "Storage",
  },
  {
    key: "chipset",
    label: "Chipset",
    sources: ["chipset"],
    importance: "high",
    group: "Performance",
  },
  {
    key: "screen_size",
    label: "Display Size",
    sources: ["screen_inch", "screen_size_inch"],
    importance: "high",
    group: "Display",
  },
  {
    key: "display_type",
    label: "Display Type",
    sources: ["display_type", "panel_type"],
    importance: "normal",
    group: "Display",
  },
  {
    key: "refresh_rate_hz",
    label: "Refresh Rate",
    sources: ["refresh_rate_hz"],
    importance: "normal",
    group: "Display",
  },
  {
    key: "network_generation",
    label: "Network",
    sources: ["network_generation"],
    importance: "high",
    group: "Connectivity",
  },
  {
    key: "battery",
    label: "Battery",
    sources: ["battery_mah", "battery_hours"],
    importance: "normal",
    group: "Battery",
  },
  {
    key: "camera",
    label: "Camera",
    sources: ["camera_summary", "rear_camera_mp"],
    importance: "normal",
    group: "Camera",
  },
];

const TELEVISION_ROWS: CompareSpecRowDef[] = [
  {
    key: "screen_size_inch",
    label: "Screen Size",
    sources: ["screen_size_inch"],
    importance: "critical",
    group: "Display",
  },
  {
    key: "panel_type",
    label: "Panel Type",
    sources: ["panel_type"],
    importance: "high",
    group: "Display",
  },
  {
    key: "resolution",
    label: "Resolution",
    sources: ["resolution"],
    importance: "high",
    group: "Display",
  },
  {
    key: "refresh_rate_hz",
    label: "Refresh Rate",
    sources: ["refresh_rate_hz"],
    importance: "high",
    group: "Display",
  },
  {
    key: "smart_platform",
    label: "Smart Platform",
    sources: ["smart_platform"],
    importance: "normal",
    group: "Features",
  },
  { key: "hdr", label: "HDR", sources: ["hdr"], importance: "normal", group: "Features" },
];

const REFRIGERATOR_ROWS: CompareSpecRowDef[] = [
  {
    key: "capacity_l",
    label: "Capacity",
    sources: ["capacity_l"],
    importance: "critical",
    group: "Capacity",
  },
  {
    key: "door_type",
    label: "Door Type",
    sources: ["door_type"],
    importance: "high",
    group: "Design",
  },
  {
    key: "frost_type",
    label: "Frost Type",
    sources: ["frost_type"],
    importance: "high",
    group: "Features",
  },
  {
    key: "star_rating",
    label: "Star Rating",
    sources: ["star_rating"],
    importance: "high",
    group: "Features",
  },
  {
    key: "compressor",
    label: "Compressor",
    sources: ["compressor_type", "inverter"],
    importance: "normal",
    group: "Performance",
  },
];

const WASHING_MACHINE_ROWS: CompareSpecRowDef[] = [
  {
    key: "capacity_kg",
    label: "Capacity",
    sources: ["capacity_kg"],
    importance: "critical",
    group: "Capacity",
  },
  {
    key: "load_type",
    label: "Load Type",
    sources: ["load_type"],
    importance: "critical",
    group: "Design",
  },
  {
    key: "automation_type",
    label: "Automation",
    sources: ["automation_type"],
    importance: "high",
    group: "Features",
  },
  {
    key: "star_rating",
    label: "Star Rating",
    sources: ["star_rating"],
    importance: "high",
    group: "Features",
  },
  { key: "rpm", label: "RPM", sources: ["rpm"], importance: "normal", group: "Performance" },
];

const TWS_ROWS: CompareSpecRowDef[] = [
  { key: "anc", label: "ANC", sources: ["anc"], importance: "high", group: "Audio" },
  { key: "codec", label: "Codec", sources: ["codec"], importance: "normal", group: "Audio" },
  {
    key: "bluetooth_version",
    label: "Bluetooth",
    sources: ["bluetooth_version"],
    importance: "normal",
    group: "Connectivity",
  },
  {
    key: "battery_hours",
    label: "Battery Hours",
    sources: ["battery_hours"],
    importance: "high",
    group: "Battery",
  },
  {
    key: "generation",
    label: "Generation",
    sources: ["generation"],
    importance: "high",
    group: "Features",
  },
  {
    key: "water_resistance",
    label: "Water Resistance",
    sources: ["water_resistance", "ip_rating"],
    importance: "normal",
    group: "Design",
  },
];

const HEADPHONE_ROWS: CompareSpecRowDef[] = [
  {
    key: "form_factor",
    label: "Form Factor",
    sources: ["form_factor"],
    importance: "critical",
    group: "Design",
  },
  {
    key: "connectivity",
    label: "Connectivity",
    sources: ["connectivity"],
    importance: "critical",
    group: "Connectivity",
  },
  { key: "anc", label: "ANC", sources: ["anc"], importance: "high", group: "Audio" },
  { key: "codec", label: "Codec", sources: ["codec"], importance: "normal", group: "Audio" },
  {
    key: "battery_hours",
    label: "Battery",
    sources: ["battery_hours"],
    importance: "high",
    group: "Battery",
  },
  {
    key: "bluetooth_version",
    label: "Bluetooth",
    sources: ["bluetooth_version"],
    importance: "normal",
    group: "Connectivity",
  },
  {
    key: "generation",
    label: "Generation",
    sources: ["generation"],
    importance: "high",
    group: "Features",
  },
];

const CAMERA_ROWS: CompareSpecRowDef[] = [
  {
    key: "camera_type",
    label: "Camera Type",
    sources: ["camera_type"],
    importance: "high",
    group: "Camera",
  },
  {
    key: "sensor_format",
    label: "Sensor Format",
    sources: ["sensor_format"],
    importance: "high",
    group: "Camera",
  },
  {
    key: "megapixels",
    label: "Megapixels",
    sources: ["megapixels"],
    importance: "high",
    group: "Camera",
  },
  { key: "mount", label: "Mount", sources: ["mount"], importance: "high", group: "Features" },
  {
    key: "body_only",
    label: "Body / Kit",
    sources: ["body_only"],
    importance: "critical",
    group: "Features",
  },
  {
    key: "kit_lens",
    label: "Kit Lens",
    sources: ["kit_lens"],
    importance: "critical",
    group: "Features",
  },
  {
    key: "video_resolution",
    label: "Video",
    sources: ["video_resolution"],
    importance: "normal",
    group: "Camera",
  },
  {
    key: "stabilization",
    label: "Stabilization",
    sources: ["stabilization", "ibis"],
    importance: "normal",
    group: "Features",
  },
];

const REGISTRY: Record<PublicCategorySlug, CompareSpecRowDef[]> = {
  laptop: LAPTOP_ROWS,
  smartphone: SMARTPHONE_ROWS,
  television: TELEVISION_ROWS,
  refrigerator: REFRIGERATOR_ROWS,
  washing_machine: WASHING_MACHINE_ROWS,
  tws: TWS_ROWS,
  headphones: HEADPHONE_ROWS,
  camera: CAMERA_ROWS,
};

export function comparisonRowsFor(category: string | null | undefined): CompareSpecRowDef[] {
  const slug = (category || "").toLowerCase() as PublicCategorySlug;
  return REGISTRY[slug] ?? [];
}

function readSpecValue(product: Product, key: string): unknown {
  const display = product.display_specs;
  if (display && key in display && display[key] != null && display[key] !== "") {
    return display[key];
  }
  const specs = product.specs as Record<string, unknown>;
  if (specs && key in specs && specs[key] != null && specs[key] !== "") {
    return specs[key];
  }
  return undefined;
}

export function formatCompareSpecValue(product: Product, row: CompareSpecRowDef): string | null {
  for (const source of row.sources) {
    const raw = readSpecValue(product, source);
    if (raw === undefined || raw === null || raw === "") continue;
    if (Array.isArray(raw)) {
      const joined = raw
        .map((item) => formatFacetValue(source, item))
        .filter(Boolean)
        .join(", ");
      if (joined) return joined;
      continue;
    }
    const formatted = formatFacetValue(source, raw);
    if (formatted) return formatted;
  }
  return null;
}

export type ResolvedCompareRow = {
  def: CompareSpecRowDef;
  values: Array<string | null>;
  differs: boolean;
  allMissing: boolean;
};

export function resolveCompareRows(
  category: string | null | undefined,
  products: readonly Product[],
): ResolvedCompareRow[] {
  if (products.length === 0) return [];
  const defs = comparisonRowsFor(category);
  return defs
    .map((def) => {
      const values = products.map((product) => formatCompareSpecValue(product, def));
      const present = values.filter((value) => value != null && value !== "");
      const allMissing = present.length === 0;
      const unique = new Set(present.map((value) => value!.toLowerCase()));
      const differs = !allMissing && (unique.size > 1 || present.length < products.length);
      return { def, values, differs, allMissing };
    })
    .filter((row) => !row.allMissing);
}

export function keyDifferenceRows(
  rows: readonly ResolvedCompareRow[],
  limit = 6,
): ResolvedCompareRow[] {
  const ranked = [...rows]
    .filter((row) => row.differs)
    .sort((a, b) => {
      const rank = (importance: CompareSpecImportance) =>
        importance === "critical" ? 0 : importance === "high" ? 1 : 2;
      return rank(a.def.importance) - rank(b.def.importance);
    });
  return ranked.slice(0, limit);
}

/** Spec groups present in resolved rows, stable category order. */
export function presentCompareGroups(rows: readonly ResolvedCompareRow[]): CompareSpecGroup[] {
  const seen = new Set<CompareSpecGroup>();
  const ordered: CompareSpecGroup[] = [];
  for (const row of rows) {
    if (!seen.has(row.def.group)) {
      seen.add(row.def.group);
      ordered.push(row.def.group);
    }
  }
  return ordered;
}

export type CompareNavFilter = "key_differences" | "price" | "all" | CompareSpecGroup;

export function filterCompareRows(
  rows: readonly ResolvedCompareRow[],
  filter: CompareNavFilter,
): ResolvedCompareRow[] {
  if (filter === "all" || filter === "price") return [...rows];
  if (filter === "key_differences") return rows.filter((row) => row.differs);
  return rows.filter((row) => row.def.group === filter);
}

export function priceDifferenceLabel(products: readonly Product[]): string | null {
  const prices = products
    .map((product) => product.best_price)
    .filter(
      (price): price is number => typeof price === "number" && Number.isFinite(price) && price > 0,
    );
  if (prices.length < 2) return null;
  const max = Math.max(...prices);
  const min = Math.min(...prices);
  const delta = max - min;
  if (delta <= 0) return null;
  return delta.toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });
}

/**
 * Compact factual line when two products differ in price and critical/high specs.
 * Neutral — no better/worse framing. Returns null when data is insufficient.
 */
export function payingExtraLine(
  products: readonly Product[],
  keyRows: readonly ResolvedCompareRow[],
): string | null {
  if (products.length !== 2) return null;
  const [a, b] = products;
  if (!a || !b) return null;
  if (!validPrice(a.best_price) || !validPrice(b.best_price)) return null;
  if (a.best_price === b.best_price) return null;

  const priceA = a.best_price;
  const priceB = b.best_price;
  const dearerIndex = priceA > priceB ? 0 : 1;
  const cheaperIndex = dearerIndex === 0 ? 1 : 0;
  const delta = Math.abs(priceA - priceB);
  if (delta < 100) return null;

  const diffs = keyRows
    .filter(
      (row) =>
        row.differs &&
        (row.def.importance === "critical" || row.def.importance === "high") &&
        row.values[dearerIndex] &&
        row.values[cheaperIndex],
    )
    .slice(0, 2);
  if (diffs.length === 0) return null;

  const bits = diffs.map((row) => {
    const dearer = row.values[dearerIndex];
    const cheaper = row.values[cheaperIndex];
    return `${row.def.label} ${dearer} vs ${cheaper}`;
  });

  return `${formatPrice(delta)} more · differs by ${bits.join(" · ")}`;
}

export { facetLabel };

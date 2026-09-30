/** Facet key labels and value formatting for search filters / display specs. */

import { formatSpecValue } from "~/lib/search/format-spec";

const FACET_LABELS: Record<string, string> = {
  brand: "Brand",
  category: "Category",
  ram_gb: "RAM",
  storage_gb: "Storage",
  screen_inch: "Screen Size",
  screen_size_inch: "Screen Size",
  panel_type: "Panel",
  resolution: "Resolution",
  refresh_rate_hz: "Refresh Rate",
  capacity_l: "Capacity",
  capacity_kg: "Capacity",
  door_type: "Door Type",
  frost_type: "Frost",
  star_rating: "Star Rating",
  load_type: "Load Type",
  automation_type: "Type",
  rpm: "RPM",
  network_generation: "Network",
  chipset: "Chipset",
  form_factor: "Form Factor",
  connectivity: "Connectivity",
  anc: "ANC",
  generation: "Generation",
  codec: "Codec",
  cpu_series: "Processor",
  gpu: "Graphics",
  camera_type: "Type",
  sensor_format: "Sensor",
  megapixels: "Megapixels",
  mount: "Mount",
  body_only: "Body / Kit",
  kit_lens: "Kit Lens",
};

export function facetLabel(key: string): string {
  return FACET_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatFacetValue(key: string, value: unknown): string {
  return formatSpecValue(key, value);
}

export function formatDisplaySpecEntry(key: string, value: unknown): string | null {
  const formatted = formatFacetValue(key, value);
  if (!formatted) return null;
  if (key === "anc" && (formatted === "ANC" || formatted === "No ANC")) return formatted;
  if (
    key === "ram_gb" ||
    key === "storage_gb" ||
    key === "screen_inch" ||
    key === "screen_size_inch" ||
    key === "capacity_l" ||
    key === "capacity_kg"
  ) {
    return formatted;
  }
  const label = facetLabel(key);
  if (formatted.toLowerCase().includes(label.toLowerCase())) return formatted;
  return `${label}: ${formatted}`;
}

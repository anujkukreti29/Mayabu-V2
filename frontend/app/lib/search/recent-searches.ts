/** Recent searches — local only, bounded, no server sync. */

const STORAGE_KEY = "mayabu:recent-searches:v1";
const MAX_RECENT = 8;

export function readRecentSearches(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => String(item || "").trim())
      .filter((item) => item.length >= 2 && item.length <= 160)
      .slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

export function pushRecentSearch(query: string): string[] {
  const trimmed = query.trim().slice(0, 160);
  if (trimmed.length < 2) return readRecentSearches();
  const next = [trimmed, ...readRecentSearches().filter((item) => item.toLowerCase() !== trimmed.toLowerCase())].slice(
    0,
    MAX_RECENT,
  );
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Quota / private mode — ignore.
  }
  return next;
}

export function removeRecentSearch(query: string): string[] {
  const next = readRecentSearches().filter((item) => item.toLowerCase() !== query.trim().toLowerCase());
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // ignore
  }
  return next;
}

export function clearRecentSearches(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

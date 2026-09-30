export function safeNextPath(value: string | null | undefined, fallback = "/account"): string {
  if (!value) return fallback;
  const candidate = value.trim();
  if (!candidate.startsWith("/") || candidate.startsWith("//")) return fallback;
  if (candidate.includes("://")) return fallback;
  if (!/^\/[a-zA-Z0-9/_?&=.\-~%]*$/.test(candidate)) return fallback;
  return candidate;
}

/** Mask an email for shared/public UI surfaces (keeps domain). */
export function maskEmail(email: string): string {
  const trimmed = email.trim();
  const at = trimmed.indexOf("@");
  if (at <= 0) return "***";
  const local = trimmed.slice(0, at);
  const domain = trimmed.slice(at + 1);
  const visible = local.slice(0, 1);
  return `${visible}***@${domain}`;
}

/** Map API errors to auth-safe user copy. */
export function authErrorMessage(error: unknown, fallback: string): string {
  if (
    error &&
    typeof error === "object" &&
    "category" in error &&
    (error as { category?: string }).category === "rate-limit"
  ) {
    const retry = (error as { retryAfterSeconds?: number }).retryAfterSeconds;
    if (typeof retry === "number" && retry > 0) {
      const minutes = Math.max(1, Math.ceil(retry / 60));
      return `Too many attempts. Try again in about ${minutes} minute${minutes === 1 ? "" : "s"}.`;
    }
    return "Too many attempts. Try again in a few minutes.";
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

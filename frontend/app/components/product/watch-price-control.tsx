import { Bell, ChevronDown } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "~/components/auth/auth-provider";
import { Button } from "~/components/ui/button";
import { cn } from "~/components/ui/cn";
import {
  addWishlistItem,
  fetchWishlist,
  updateWishlistWatch,
} from "~/lib/api/auth";
import type { Product } from "~/lib/api/schemas";
import { formatPrice, validPrice } from "~/lib/formatting/price";
import { routes } from "~/lib/navigation/routes";

const MAX_TARGET = 10_000_000;

function watchStorageKey(productId: string) {
  return `mayabu-watch-v1:${productId}`;
}

function readStoredWatch(productId: string): { target: number | null; notifyOnDrop: boolean } | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(watchStorageKey(productId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { target?: number | null; notifyOnDrop?: boolean };
    const target =
      typeof parsed.target === "number" && Number.isFinite(parsed.target) ? parsed.target : null;
    const notifyOnDrop = Boolean(parsed.notifyOnDrop);
    if (target == null && !notifyOnDrop) return null;
    return { target, notifyOnDrop };
  } catch {
    return null;
  }
}

function writeStoredWatch(
  productId: string,
  value: { target: number | null; notifyOnDrop: boolean } | null,
) {
  if (typeof window === "undefined") return;
  try {
    if (!value) {
      window.sessionStorage.removeItem(watchStorageKey(productId));
      return;
    }
    window.sessionStorage.setItem(watchStorageKey(productId), JSON.stringify(value));
  } catch {
    /* optional */
  }
}

export function parseTargetPriceInput(raw: string): { ok: true; value: number } | { ok: false; error: string } {
  const cleaned = raw.replace(/[₹,\s]/g, "").trim();
  if (!cleaned) return { ok: false, error: "Enter a target price in rupees." };
  const value = Number(cleaned);
  if (!Number.isFinite(value) || value <= 0) {
    return { ok: false, error: "Target price must be a positive number." };
  }
  if (value > MAX_TARGET) {
    return { ok: false, error: "Target price is too high." };
  }
  return { ok: true, value: Math.round(value) };
}

export function WatchPriceControl({
  productId,
  productTitle,
  currentPrice,
  initialTarget = null,
  initialNotifyOnDrop = false,
  className,
}: {
  productId: string;
  productTitle?: string | null;
  currentPrice?: number | null;
  initialTarget?: number | null;
  initialNotifyOnDrop?: boolean;
  className?: string;
}) {
  const auth = useAuth();
  const navigate = useNavigate();
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"drop" | "target">(
    initialTarget != null ? "target" : "drop",
  );
  const [targetInput, setTargetInput] = useState(
    initialTarget != null ? String(Math.round(initialTarget)) : "",
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<{
    target: number | null;
    notifyOnDrop: boolean;
  } | null>(() => {
    if (initialNotifyOnDrop || initialTarget != null) {
      return { target: initialTarget, notifyOnDrop: initialNotifyOnDrop };
    }
    return readStoredWatch(productId);
  });
  const [hydrateReady, setHydrateReady] = useState(
    !auth.user || initialNotifyOnDrop || initialTarget != null,
  );

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, [open]);

  useEffect(() => {
    if (!auth.user) {
      setHydrateReady(true);
      return;
    }
    let cancelled = false;
    setHydrateReady(false);
    void fetchWishlist()
      .then((payload) => {
        if (cancelled) return;
        const row = payload.products.find((item) => item.id === productId) as
          | (Product & { target_price?: number | null; notify_on_drop?: boolean })
          | undefined;
        if (!row) {
          setSaved(null);
          writeStoredWatch(productId, null);
          setHydrateReady(true);
          return;
        }
        const target =
          typeof row.target_price === "number" && Number.isFinite(row.target_price)
            ? row.target_price
            : null;
        const notifyOnDrop = Boolean(row.notify_on_drop);
        if (target != null || notifyOnDrop) {
          const next = { target, notifyOnDrop };
          setSaved(next);
          writeStoredWatch(productId, next);
          if (target != null) {
            setMode("target");
            setTargetInput(String(Math.round(target)));
          }
        } else {
          setSaved(null);
          writeStoredWatch(productId, null);
        }
        setHydrateReady(true);
      })
      .catch(() => {
        if (!cancelled) setHydrateReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.user, productId]);

  const watching = Boolean(saved?.notifyOnDrop || saved?.target != null);
  const summary =
    auth.user && !hydrateReady && !watching
      ? "Loading watch…"
      : watching
        ? saved?.target != null
          ? `Watching · Target ${formatPrice(saved.target)}`
          : "Watching meaningful drops"
        : "Watch price";

  async function ensureWishlisted(): Promise<boolean> {
    if (auth.isWishlisted(productId)) return true;
    try {
      const result = await addWishlistItem(productId);
      auth.markWishlisted(productId, true);
      auth.setSession(auth.user, result.count);
      return true;
    } catch {
      setError("Could not save this product. Try again.");
      return false;
    }
  }

  async function saveWatch() {
    if (!auth.user) {
      void navigate(
        `${routes.login}?next=${encodeURIComponent(
          typeof window !== "undefined" ? window.location.pathname : "/wishlist",
        )}`,
      );
      return;
    }
    setError(null);
    let target: number | null = null;
    let notifyOnDrop = mode === "drop";
    if (mode === "target") {
      const parsed = parseTargetPriceInput(targetInput);
      if (!parsed.ok) {
        setError(parsed.error);
        return;
      }
      target = parsed.value;
      notifyOnDrop = false;
      if (validPrice(currentPrice) && target >= currentPrice) {
        setError("Choose a target below the current listed price.");
        return;
      }
    }

    setSaving(true);
    const previous = saved;
    setSaved({ target, notifyOnDrop });
    try {
      const ready = await ensureWishlisted();
      if (!ready) {
        setSaved(previous);
        return;
      }
      await updateWishlistWatch(productId, {
        target_price: target,
        notify_on_drop: notifyOnDrop,
      });
      writeStoredWatch(productId, { target, notifyOnDrop });
      setOpen(false);
    } catch {
      setSaved(previous);
      setError("Could not save price watch. Try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        className={cn(
          "inline-flex min-h-11 items-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-semibold text-ink transition",
          "hover:border-brand-300 hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
          watching && "border-brand-300 text-brand-700",
        )}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          if (!auth.user) {
            void navigate(
              `${routes.login}?next=${encodeURIComponent(
                typeof window !== "undefined" ? window.location.pathname : "/wishlist",
              )}`,
            );
            return;
          }
          setOpen((value) => !value);
        }}
      >
        <Bell aria-hidden="true" className={cn("h-4 w-4", watching && "text-brand-700")} />
        <span data-testid="watch-price-label">{summary}</span>
        <ChevronDown aria-hidden="true" className={cn("h-4 w-4", open && "rotate-180")} />
      </button>

      {open ? (
        <div
          id={panelId}
          role="dialog"
          aria-label={`Watch price for ${productTitle || "product"}`}
          className="absolute left-0 z-40 mt-2 w-[min(100vw-2rem,20rem)] rounded-md border border-line bg-white p-3 shadow-lift"
        >
          <p className="text-sm font-semibold text-ink">Save price watch</p>
          <p className="mt-1 text-xs leading-5 text-ink-muted">
            Mayabu tracks this watch inside your account. External email alerts are not sent until
            the notification provider is operational.
          </p>

          <fieldset className="mt-3 space-y-2">
            <legend className="sr-only">Watch mode</legend>
            <div className="flex items-start gap-2 text-sm text-ink">
              <input
                id={`${panelId}-drop`}
                type="radio"
                name={`${panelId}-mode`}
                checked={mode === "drop"}
                onChange={() => setMode("drop")}
                className="mt-1"
              />
              <label htmlFor={`${panelId}-drop`} className="cursor-pointer">
                <span className="font-medium">Any meaningful drop</span>
                <span className="mt-0.5 block text-xs text-ink-muted">
                  Track when Mayabu sees a clear downward move.
                </span>
              </label>
            </div>
            <div className="flex items-start gap-2 text-sm text-ink">
              <input
                id={`${panelId}-target-mode`}
                type="radio"
                name={`${panelId}-mode`}
                checked={mode === "target"}
                onChange={() => setMode("target")}
                className="mt-1"
              />
              <label htmlFor={`${panelId}-target-mode`} className="cursor-pointer font-medium">
                Target price
              </label>
            </div>
          </fieldset>

          {mode === "target" ? (
            <div className="mt-2 text-sm">
              <label htmlFor={`${panelId}-target`} className="sr-only">
                Target price in rupees
              </label>
              <span className="text-ink-muted" aria-hidden="true">
                ₹
              </span>
              <input
                id={`${panelId}-target`}
                type="text"
                inputMode="numeric"
                value={targetInput}
                onChange={(event) => setTargetInput(event.target.value)}
                placeholder="49,999"
                className="ml-1 w-[calc(100%-1.25rem)] rounded-md border border-line px-2 py-1.5 text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
          ) : null}

          {error ? (
            <p className="mt-2 text-xs text-rose-700" role="alert">
              {error}
            </p>
          ) : null}

          <div className="mt-3 flex gap-2">
            <Button type="button" size="sm" disabled={saving} onClick={() => void saveWatch()}>
              {saving
                ? "Saving…"
                : mode === "target"
                  ? "Track this target"
                  : "Save price watch"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

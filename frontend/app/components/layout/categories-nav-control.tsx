import { ChevronDown } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { CategoriesMegaMenu } from "~/components/layout/categories-mega-menu";
import { cn } from "~/components/ui/cn";

const CLOSE_DELAY_MS = 160;

/**
 * Desktop Categories control: open on hover, click, and keyboard focus.
 * Shared hover region + short close delay prevents flicker across the gap.
 */
export function CategoriesNavControl() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | null>(null);
  const ignoreClickToggle = useRef(false);
  const menuId = useId();
  const finePointer = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    finePointer.current = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  }, []);

  const clearCloseTimer = () => {
    if (closeTimer.current != null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  const scheduleClose = () => {
    clearCloseTimer();
    closeTimer.current = window.setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  };

  const openNow = () => {
    clearCloseTimer();
    setOpen(true);
  };

  useEffect(() => () => clearCloseTimer(), []);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        rootRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
      }
    };
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open]);

  return (
    <div
      ref={rootRef}
      className="relative"
      onPointerEnter={() => {
        if (finePointer.current) {
          ignoreClickToggle.current = true;
          openNow();
        }
      }}
      onPointerLeave={() => {
        if (finePointer.current) scheduleClose();
      }}
    >
      <button
        type="button"
        className={cn("nav-link gap-1", open && "nav-link-active")}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => {
          clearCloseTimer();
          if (ignoreClickToggle.current) {
            ignoreClickToggle.current = false;
            setOpen(true);
            return;
          }
          setOpen((value) => !value);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            openNow();
          } else if ((event.key === "Enter" || event.key === " ") && !open) {
            event.preventDefault();
            openNow();
          } else if ((event.key === "Enter" || event.key === " ") && open) {
            event.preventDefault();
            setOpen(false);
          }
        }}
      >
        Categories <ChevronDown aria-hidden="true" className="h-3.5 w-3.5 opacity-80" />
      </button>
      {open ? (
        <div
          id={menuId}
          role="navigation"
          aria-label="Product categories"
          className="absolute left-0 top-full z-[60] pt-2"
          onFocus={openNow}
        >
          <div className="w-[min(92vw,30rem)] rounded-md border border-line bg-white p-3.5 text-ink shadow-lift sm:p-4">
            <p className="mb-2 px-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
              Browse categories
            </p>
            <CategoriesMegaMenu onNavigate={() => setOpen(false)} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

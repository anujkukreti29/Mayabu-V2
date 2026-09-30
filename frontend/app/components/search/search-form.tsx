import { Clock3, Search, Tag, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useNavigate } from "react-router";
import { Button } from "~/components/ui/button";
import { cn } from "~/components/ui/cn";
import { SearchSuggestionSkeleton } from "~/components/ui/skeleton";
import { ProductImage } from "~/components/product/product-image";
import { searchSuggest } from "~/lib/api/search";
import type { SearchSuggestResponse } from "~/lib/api/schemas";
import { formatPrice, validPrice } from "~/lib/formatting/price";
import { categoryLandingPath } from "~/lib/category/landing-registry";
import { categoryShortLabel } from "~/lib/search/categories";
import { variantIdentityLine } from "~/lib/search/format-spec";
import {
  clearRecentSearches,
  pushRecentSearch,
  readRecentSearches,
  removeRecentSearch,
} from "~/lib/search/recent-searches";
import { productSlug } from "~/lib/seo/slug";

const DEFAULT_PLACEHOLDER = "Search products, brands and models…";
const DEFAULT_SUBMIT = "Search";
const DEFAULT_LABEL = "Search Mayabu products";
const DEBOUNCE_MS = 220;
const MIN_QUERY = 2;

type SuggestionItem =
  | { kind: "product"; id: string; href: string; label: string }
  | { kind: "category"; id: string; href: string; label: string }
  | { kind: "recent"; id: string; query: string; label: string }
  | { kind: "popular"; id: string; query: string; label: string }
  | { kind: "search_all"; id: string; query: string; label: string };

function productHref(id: string, title: string): string {
  return `/products/${id}/${productSlug(title || "product")}`;
}

function configLine(product: {
  category?: string | null;
  display_specs?: Record<string, unknown>;
  specs?: Record<string, unknown>;
  model_codes?: string[];
  title?: string;
}): string | null {
  return variantIdentityLine({
    id: "suggest",
    title: product.title || "",
    category: product.category,
    display_specs: product.display_specs,
    specs: product.specs,
    model_codes: product.model_codes,
  } as Parameters<typeof variantIdentityLine>[0]);
}

export function SearchForm({
  defaultValue = "",
  compact = false,
  placeholder,
  submitLabel,
  hiddenFields,
  tone = "light",
  inputId,
}: {
  defaultValue?: string;
  compact?: boolean;
  placeholder?: string;
  submitLabel?: string;
  /** Preserve category/filters/sort when resubmitting from the search box. */
  hiddenFields?: Record<string, string | undefined | null>;
  /** `header` = unified control for dark navbar; `light` = hero/page surfaces. */
  tone?: "light" | "header";
  inputId?: string;
}) {
  const navigate = useNavigate();
  const autoId = useId();
  const listboxId = `${autoId}-listbox`;
  const resolvedPlaceholder = placeholder ?? DEFAULT_PLACEHOLDER;
  const resolvedSubmitLabel = submitLabel ?? DEFAULT_SUBMIT;
  // Prefer caller inputId when unique; otherwise React useId avoids collisions when
  // multiple SearchForms mount (header + page, etc.).
  const resolvedInputId = inputId ?? `${autoId}-input`;
  const isHeader = tone === "header";

  const [query, setQuery] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [suggest, setSuggest] = useState<SearchSuggestResponse | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [fetchError, setFetchError] = useState(false);

  const rootRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    setQuery(defaultValue);
  }, [defaultValue]);

  useEffect(() => {
    setRecent(readRecentSearches());
  }, []);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setActiveIndex(-1);
      }
    };
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const trimmed = query.trim();
    const requestId = ++requestIdRef.current;
    abortRef.current?.abort();

    if (trimmed.length < MIN_QUERY) {
      // Idle open: show recent + optional popular/categories from empty suggest.
      const controller = new AbortController();
      abortRef.current = controller;
      setLoading(true);
      setFetchError(false);
      const timer = window.setTimeout(() => {
        void searchSuggest("", controller.signal, 6)
          .then((payload) => {
            if (requestId !== requestIdRef.current) return;
            setSuggest(payload);
            setLoading(false);
          })
          .catch((error: unknown) => {
            if (controller.signal.aborted || requestId !== requestIdRef.current) return;
            setSuggest(null);
            setFetchError(true);
            setLoading(false);
            void error;
          });
      }, 0);
      return () => {
        window.clearTimeout(timer);
        controller.abort();
      };
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setFetchError(false);
    const timer = window.setTimeout(() => {
      void searchSuggest(trimmed, controller.signal, 6)
        .then((payload) => {
          if (requestId !== requestIdRef.current) return;
          setSuggest(payload);
          setLoading(false);
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted || requestId !== requestIdRef.current) return;
          setSuggest(null);
          setFetchError(true);
          setLoading(false);
          void error;
        });
    }, DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, open]);

  const trimmed = query.trim();
  const products = suggest?.products ?? [];
  const categories = suggest?.categories ?? [];
  const popular = suggest?.popular_queries ?? [];
  const showRecent = trimmed.length < MIN_QUERY && recent.length > 0;
  const showPopular = trimmed.length < MIN_QUERY && popular.length > 0;
  const showCategories = categories.length > 0;
  const showProducts = trimmed.length >= MIN_QUERY && products.length > 0;
  const showEmptyHint =
    open &&
    trimmed.length >= MIN_QUERY &&
    !loading &&
    !fetchError &&
    products.length === 0 &&
    categories.length === 0;

  const items: SuggestionItem[] = [];
  if (showRecent) {
    for (const entry of recent) {
      items.push({ kind: "recent", id: `recent:${entry}`, query: entry, label: entry });
    }
  }
  if (showPopular) {
    for (const entry of popular) {
      const q = entry.query?.trim();
      if (!q) continue;
      items.push({ kind: "popular", id: `popular:${q}`, query: q, label: q });
    }
  }
  if (showCategories) {
    for (const cat of categories) {
      const href = categoryLandingPath(cat.slug) ?? `/search?category=${encodeURIComponent(cat.slug)}`;
      items.push({ kind: "category", id: `cat:${cat.slug}`, href, label: cat.label });
    }
  }
  if (showProducts) {
    for (const product of products) {
      items.push({
        kind: "product",
        id: `product:${product.id}`,
        href: productHref(product.id, product.title),
        label: product.title || "Product",
      });
    }
  }
  if (showEmptyHint || (trimmed.length >= MIN_QUERY && open && !loading)) {
    items.push({
      kind: "search_all",
      id: "search_all",
      query: trimmed,
      label: showEmptyHint
        ? "No matching products yet. Press Enter to search all results."
        : `Search all results for “${trimmed}”`,
    });
  }

  const activeDescendant =
    activeIndex >= 0 && activeIndex < items.length ? `${listboxId}-option-${activeIndex}` : undefined;

  function closePanel() {
    setOpen(false);
    setActiveIndex(-1);
  }

  function goSearch(q: string) {
    const next = q.trim().slice(0, 160);
    if (next.length < MIN_QUERY) return;
    setRecent(pushRecentSearch(next));
    closePanel();
    const params = new URLSearchParams();
    params.set("q", next);
    if (hiddenFields) {
      for (const [name, value] of Object.entries(hiddenFields)) {
        if (value) params.set(name, value);
      }
    }
    void navigate(`/search?${params.toString()}`);
  }

  function activateItem(item: SuggestionItem) {
    if (item.kind === "product" || item.kind === "category") {
      if (trimmed.length >= MIN_QUERY) setRecent(pushRecentSearch(trimmed));
      closePanel();
      void navigate(item.href);
      return;
    }
    goSearch(item.query);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    const next = query.trim();
    if (next.length < MIN_QUERY) {
      event.preventDefault();
      return;
    }
    if (activeIndex >= 0 && activeIndex < items.length && open) {
      event.preventDefault();
      activateItem(items[activeIndex]!);
      return;
    }
    setRecent(pushRecentSearch(next));
    closePanel();
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      if (open) {
        event.preventDefault();
        closePanel();
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        setActiveIndex(0);
        return;
      }
      if (items.length === 0) return;
      setActiveIndex((index) => (index + 1) % items.length);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open || items.length === 0) return;
      setActiveIndex((index) => (index <= 0 ? items.length - 1 : index - 1));
      return;
    }
    if (event.key === "Enter" && open && activeIndex >= 0 && activeIndex < items.length) {
      event.preventDefault();
      activateItem(items[activeIndex]!);
    }
  }

  return (
    <div ref={rootRef} className={cn("relative w-full", !compact && !isHeader && "max-w-3xl")}>
      <form
        method="get"
        action="/search"
        role="search"
        className="w-full"
        onSubmit={onSubmit}
      >
        <label className="sr-only" htmlFor={resolvedInputId}>
          {DEFAULT_LABEL}
        </label>
        <div
          className={cn(
            "flex w-full min-w-0 items-stretch overflow-hidden rounded-md border bg-white shadow-sm",
            isHeader
              ? "border-white/20 bg-white focus-within:border-accent focus-within:shadow-focus"
              : "border-line focus-within:border-accent focus-within:shadow-focus",
            compact ? "min-h-10" : "min-h-12",
          )}
        >
          <span
            className={cn(
              "grid shrink-0 place-items-center text-ink-muted",
              compact ? "w-10" : "w-11",
            )}
            aria-hidden="true"
          >
            <Search className={cn(compact ? "h-4 w-4" : "h-5 w-5")} />
          </span>
          <input
            id={resolvedInputId}
            name="q"
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
              setActiveIndex(-1);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
            minLength={2}
            maxLength={160}
            autoComplete="off"
            spellCheck={false}
            role="combobox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-activedescendant={activeDescendant}
            aria-haspopup="listbox"
            placeholder={resolvedPlaceholder}
            className={cn(
              "min-w-0 flex-1 border-0 bg-transparent text-ink placeholder:text-ink-muted focus:outline-none focus:ring-0",
              compact ? "py-2 text-sm" : "py-2.5 text-base",
            )}
          />
          {hiddenFields
            ? Object.entries(hiddenFields).map(([name, value]) =>
                value ? <input key={name} type="hidden" name={name} value={value} /> : null,
              )
            : null}
          <Button
            type="submit"
            size={compact ? "sm" : "md"}
            aria-label={DEFAULT_LABEL}
            className={cn(
              "shrink-0 rounded-none border-0 border-l",
              isHeader ? "border-line/80" : "border-line",
              compact ? "min-h-10 px-3 text-sm" : "min-h-12 px-4",
            )}
          >
            <Search aria-hidden="true" className="h-4 w-4 sm:hidden" />
            <span className="hidden sm:inline">{resolvedSubmitLabel}</span>
          </Button>
        </div>
      </form>

      {open ? (
        <div
          id={listboxId}
          role="listbox"
          aria-label="Search suggestions"
          className={cn(
            "absolute left-0 right-0 z-50 mt-1.5 max-h-[min(70vh,28rem)] overflow-y-auto rounded-md border border-line bg-white shadow-lift",
            "opacity-100 transition duration-snappy ease-mayabu motion-reduce:transition-none",
            "sm:max-h-[min(72vh,32rem)]",
          )}
        >
          {loading && items.length === 0 ? (
            <SearchSuggestionSkeleton rows={4} />
          ) : null}

          {fetchError && trimmed.length >= MIN_QUERY ? (
            <p className="px-3 py-3 text-sm text-ink-muted" role="status">
              Suggestions unavailable. Press Enter to search all results.
            </p>
          ) : null}

          {showRecent ? (
            <section className="border-b border-line/80 px-1 py-1.5" aria-label="Recent searches">
              <div className="flex items-center justify-between px-2 pb-1 pt-1">
                <p className="text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
                  Recent
                </p>
                <button
                  type="button"
                  className="text-xs font-medium text-accent hover:underline"
                  onClick={() => {
                    clearRecentSearches();
                    setRecent([]);
                  }}
                >
                  Clear
                </button>
              </div>
              {recent.map((entry) => {
                const index = items.findIndex((item) => item.kind === "recent" && item.query === entry);
                const active = index === activeIndex;
                return (
                  <div
                    key={entry}
                    id={index >= 0 ? `${listboxId}-option-${index}` : undefined}
                    role="option"
                    aria-selected={active}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-sm px-2 py-2 text-left text-sm",
                      active ? "bg-brand-50 text-ink" : "text-ink hover:bg-surface-muted",
                    )}
                  >
                    <button
                      type="button"
                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => goSearch(entry)}
                    >
                      <Clock3 aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-ink-soft" />
                      <span className="truncate">{entry}</span>
                    </button>
                    <button
                      type="button"
                      className="shrink-0 rounded p-1 text-ink-soft hover:bg-white hover:text-ink"
                      aria-label={`Remove “${entry}” from recent searches`}
                      onClick={() => setRecent(removeRecentSearch(entry))}
                    >
                      <X className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </div>
                );
              })}
            </section>
          ) : null}

          {showPopular ? (
            <section className="border-b border-line/80 px-1 py-1.5" aria-label="Popular searches">
              <p className="px-2 pb-1 pt-1 text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
                Popular
              </p>
              {popular.map((entry) => {
                const q = entry.query?.trim();
                if (!q) return null;
                const index = items.findIndex((item) => item.kind === "popular" && item.query === q);
                const active = index === activeIndex;
                return (
                  <button
                    key={q}
                    type="button"
                    id={index >= 0 ? `${listboxId}-option-${index}` : undefined}
                    role="option"
                    aria-selected={active}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-sm px-2 py-2 text-left text-sm",
                      active ? "bg-brand-50 text-ink" : "text-ink hover:bg-surface-muted",
                    )}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => goSearch(q)}
                  >
                    <Search aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-ink-soft" />
                    <span className="truncate">{q}</span>
                  </button>
                );
              })}
            </section>
          ) : null}

          {showCategories ? (
            <section className="border-b border-line/80 px-1 py-1.5" aria-label="Categories">
              <p className="px-2 pb-1 pt-1 text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
                Categories
              </p>
              {categories.map((cat) => {
                const href =
                  categoryLandingPath(cat.slug) ?? `/search?category=${encodeURIComponent(cat.slug)}`;
                const index = items.findIndex((item) => item.kind === "category" && item.id === `cat:${cat.slug}`);
                const active = index === activeIndex;
                return (
                  <button
                    key={cat.slug}
                    type="button"
                    id={index >= 0 ? `${listboxId}-option-${index}` : undefined}
                    role="option"
                    aria-selected={active}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-sm px-2 py-2 text-left text-sm",
                      active ? "bg-brand-50 text-ink" : "text-ink hover:bg-surface-muted",
                    )}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => {
                      if (trimmed.length >= MIN_QUERY) setRecent(pushRecentSearch(trimmed));
                      closePanel();
                      void navigate(href);
                    }}
                  >
                    <Tag aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-ink-soft" />
                    <span className="truncate font-medium">{cat.label}</span>
                  </button>
                );
              })}
            </section>
          ) : null}

          {showProducts ? (
            <section className="px-1 py-1.5" aria-label="Products">
              <p className="px-2 pb-1 pt-1 text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
                Products
              </p>
              {products.map((product) => {
                const index = items.findIndex(
                  (item) => item.kind === "product" && item.id === `product:${product.id}`,
                );
                const active = index === activeIndex;
                const config = configLine(product);
                const category = categoryShortLabel(product.category);
                const price = validPrice(product.best_price) ? formatPrice(product.best_price) : null;
                const signal =
                  (product.platform_count ?? product.offer_count ?? 0) >= 2
                    ? `${product.platform_count ?? product.offer_count} stores`
                    : null;
                return (
                  <button
                    key={product.id}
                    type="button"
                    id={index >= 0 ? `${listboxId}-option-${index}` : undefined}
                    role="option"
                    aria-selected={active}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-sm px-2 py-2 text-left",
                      active ? "bg-brand-50" : "hover:bg-surface-muted",
                    )}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => {
                      if (trimmed.length >= MIN_QUERY) setRecent(pushRecentSearch(trimmed));
                      closePanel();
                      void navigate(productHref(product.id, product.title));
                    }}
                  >
                    <div className="h-11 w-11 shrink-0 overflow-hidden rounded-sm bg-surface-muted ring-1 ring-inset ring-line">
                      <ProductImage
                        src={product.image_url}
                        alt=""
                        category={product.category}
                        variant="thumb"
                        frameClassName="h-11 max-h-11"
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink">
                        {product.title || "Product"}
                      </p>
                      {config ? (
                        <p className="truncate text-xs text-ink-muted">{config}</p>
                      ) : null}
                      <p className="mt-0.5 truncate text-xs text-ink-soft">
                        {[category, signal].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    {price ? (
                      <span className="price-numerals shrink-0 text-sm font-semibold text-ink">
                        {price}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </section>
          ) : null}

          {items.some((item) => item.kind === "search_all") ? (
            <div className="border-t border-line/80 px-1 py-1.5">
              {items
                .map((item, index) => ({ item, index }))
                .filter(({ item }) => item.kind === "search_all")
                .map(({ item, index }) => (
                  <button
                    key={item.id}
                    type="button"
                    id={`${listboxId}-option-${index}`}
                    role="option"
                    aria-selected={index === activeIndex}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-sm px-2 py-2.5 text-left text-sm",
                      index === activeIndex
                        ? "bg-brand-50 text-ink"
                        : "text-ink-muted hover:bg-surface-muted",
                    )}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => {
                      if (item.kind === "search_all") goSearch(item.query);
                    }}
                  >
                    <Search aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                    <span>{item.label}</span>
                  </button>
                ))}
            </div>
          ) : null}

          {!loading &&
          !fetchError &&
          items.length === 0 &&
          trimmed.length < MIN_QUERY ? (
            <p className="px-3 py-3 text-sm text-ink-muted">
              Type at least two characters to see product suggestions.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

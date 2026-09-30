/** Premium loading skeletons — layout-stable, reduced-motion safe. */

import { cn } from "~/components/ui/cn";

export function Skeleton({ className, pulse = true }: { className?: string; pulse?: boolean }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-md bg-slate-200/90",
        pulse && "skeleton-shimmer motion-reduce:animate-none motion-reduce:bg-slate-200",
        className,
      )}
    />
  );
}

export function ProductCardSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("surface flex h-full flex-col overflow-hidden p-3", className)}
      aria-hidden="true"
    >
      <Skeleton className="aspect-[4/3] w-full rounded-md" />
      <Skeleton className="mt-3 h-3 w-1/3" />
      <Skeleton className="mt-2 h-4 w-full" />
      <Skeleton className="mt-1.5 h-4 w-[80%]" />
      <Skeleton className="mt-3 h-6 w-[40%]" />
      <div className="mt-2 flex gap-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
      <div className="mt-auto flex gap-2 pt-3">
        <Skeleton className="h-10 flex-1" />
        <Skeleton className="h-10 w-10" />
      </div>
    </div>
  );
}

export function ProductRailSkeleton({
  count = 4,
  titleWidth = "w-48",
}: {
  count?: number;
  titleWidth?: string;
}) {
  return (
    <section className="mt-10" aria-busy="true" aria-label="Loading products">
      <Skeleton className={cn("h-6", titleWidth)} />
      <Skeleton className="mt-2 h-3 w-64 max-w-full" />
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: count }, (_, i) => (
          <ProductCardSkeleton key={i} />
        ))}
      </div>
    </section>
  );
}

export function CategoryCardSkeleton() {
  return (
    <div className="surface flex flex-col gap-2 p-4" aria-hidden="true">
      <Skeleton className="h-10 w-10 rounded-lg" />
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-3 w-16" />
    </div>
  );
}

export function SearchSuggestionSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-2" aria-busy="true" aria-label="Loading suggestions">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3 px-2 py-1.5">
          <Skeleton className="h-8 w-8 rounded" />
          <div className="min-w-0 flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-[75%]" />
            <Skeleton className="h-3 w-[33%]" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function HomepageOpeningSkeleton() {
  return (
    <div className="bg-page" aria-busy="true" aria-label="Loading Mayabu homepage">
      <section className="border-b border-line hero-atmosphere">
        <div className="page-container py-8 sm:py-10">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="mt-3 h-10 w-full max-w-xl sm:h-12" />
          <Skeleton className="mt-3 h-4 w-full max-w-lg" />
          <Skeleton className="mt-5 h-12 w-full max-w-2xl rounded-lg" />
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <Skeleton className="aspect-[16/10] w-full rounded-lg sm:col-span-2" />
            <div className="grid gap-3">
              <Skeleton className="h-24 w-full rounded-lg" />
              <Skeleton className="h-24 w-full rounded-lg" />
            </div>
          </div>
        </div>
      </section>
      <div className="page-container py-8">
        <Skeleton className="h-6 w-44" />
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {Array.from({ length: 8 }, (_, i) => (
            <CategoryCardSkeleton key={i} />
          ))}
        </div>
        <ProductRailSkeleton count={4} titleWidth="w-40" />
      </div>
    </div>
  );
}

export function CategoryPageSkeleton() {
  return (
    <div className="bg-page" aria-busy="true" aria-label="Loading category">
      <section className="border-b border-line hero-atmosphere">
        <div className="page-container py-7 sm:py-9">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="mt-4 h-9 w-56" />
          <Skeleton className="mt-2 h-4 w-full max-w-xl" />
          <Skeleton className="mt-2 h-4 w-40" />
          <Skeleton className="mt-5 h-12 w-full max-w-2xl rounded-lg" />
        </div>
      </section>
      <div className="page-container py-8">
        <div className="lg:grid lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-8">
          <aside className="mb-6 hidden lg:block">
            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </aside>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 8 }, (_, i) => (
              <ProductCardSkeleton key={i} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function SearchResultsSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
      aria-busy="true"
      aria-label="Loading search results"
    >
      {Array.from({ length: count }, (_, i) => (
        <ProductCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function GallerySkeleton() {
  return (
    <div aria-hidden="true">
      <Skeleton className="aspect-square w-full rounded-lg" />
      <div className="mt-3 flex gap-2 overflow-hidden">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-14 w-14 shrink-0 rounded-md" />
        ))}
      </div>
    </div>
  );
}

export function OfferRowSkeleton() {
  return (
    <div className="flex items-center gap-3 border-b border-line py-3" aria-hidden="true">
      <Skeleton className="h-8 w-20" />
      <div className="min-w-0 flex-1 space-y-1.5">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-3 w-40" />
      </div>
      <Skeleton className="h-10 w-28" />
    </div>
  );
}

export function PdpHeroSkeleton() {
  return (
    <div className="commerce-container py-6 sm:py-8" aria-busy="true" aria-label="Loading product">
      <Skeleton className="h-3 w-48" />
      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:gap-10">
        <GallerySkeleton />
        <div className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-4 w-[66%]" />
          <Skeleton className="mt-4 h-9 w-36" />
          <Skeleton className="h-3 w-48" />
          <div className="mt-4 flex flex-wrap gap-2">
            <Skeleton className="h-11 w-36" />
            <Skeleton className="h-11 w-28" />
            <Skeleton className="h-11 w-40" />
          </div>
        </div>
      </div>
      <div className="mt-10 space-y-2">
        <Skeleton className="h-5 w-40" />
        <OfferRowSkeleton />
        <OfferRowSkeleton />
        <OfferRowSkeleton />
      </div>
    </div>
  );
}

export function PriceHistorySkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading price history">
      <div className="flex gap-2">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-8 w-14" />
        ))}
      </div>
      <Skeleton className="h-56 w-full rounded-lg" />
    </div>
  );
}

export function AccountSkeleton() {
  return (
    <div className="page-container py-8" aria-busy="true" aria-label="Loading account">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="mt-2 h-4 w-56" />
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-32 w-full rounded-lg" />
        <Skeleton className="h-32 w-full rounded-lg" />
      </div>
    </div>
  );
}

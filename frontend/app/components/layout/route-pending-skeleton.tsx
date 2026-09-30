/** Route-level pending skeletons for client navigations. */

import type { ReactNode } from "react";
import { useNavigation } from "react-router";
import {
  CategoryPageSkeleton,
  HomepageOpeningSkeleton,
  PdpHeroSkeleton,
  SearchResultsSkeleton,
  Skeleton,
} from "~/components/ui/skeleton";

function isCategoryPath(pathname: string): boolean {
  return (
    /^\/(laptops|smartphones|televisions|refrigerators|washing-machines|tws|headphones|cameras|mobile-phones)\/?$/.test(
      pathname,
    )
  );
}

export function useRoutePendingSkeleton(): ReactNode | null {
  const navigation = useNavigation();
  if (navigation.state !== "loading" || !navigation.location) return null;

  const path = navigation.location.pathname;
  if (path === "/") return <HomepageOpeningSkeleton />;
  if (path.startsWith("/search")) {
    return (
      <div className="commerce-container py-6 sm:py-8" aria-busy="true" aria-label="Loading search">
        <Skeleton className="h-12 w-full max-w-2xl rounded-lg" />
        <div className="mt-6">
          <SearchResultsSkeleton count={8} />
        </div>
      </div>
    );
  }
  if (path.startsWith("/products/")) {
    return (
      <main id="main-content" className="bg-page">
        <PdpHeroSkeleton />
      </main>
    );
  }
  if (isCategoryPath(path)) return <CategoryPageSkeleton />;
  return null;
}

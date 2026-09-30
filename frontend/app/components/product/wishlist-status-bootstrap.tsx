/** Wishlist status bootstrap for search result grids. */

import { useEffect } from "react";
import { useAuth } from "~/components/auth/auth-provider";
import { fetchWishlistStatus } from "~/lib/api/auth";

export function WishlistStatusBootstrap({ productIds }: { productIds: string[] }) {
  const auth = useAuth();
  const idsKey = productIds.join("|");

  useEffect(() => {
    if (!auth.user || productIds.length === 0) return;
    let cancelled = false;
    void fetchWishlistStatus(productIds).then((payload) => {
      if (cancelled) return;
      Object.entries(payload.status).forEach(([id, wished]) => {
        auth.markWishlisted(id, wished);
      });
    });
    return () => {
      cancelled = true;
    };
    // Intentionally keyed by serialized ids + user id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.user?.id, idsKey, auth.markWishlisted]);

  return null;
}

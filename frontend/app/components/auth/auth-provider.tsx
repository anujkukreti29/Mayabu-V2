import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import {
  addWishlistItem,
  fetchAuthMe,
  logoutAccount,
  removeWishlistItem,
  type AuthUser,
} from "~/lib/api/auth";

type AuthContextValue = {
  user: AuthUser | null;
  wishlistCount: number;
  loading: boolean;
  refresh: () => Promise<void>;
  setSession: (user: AuthUser | null, wishlistCount?: number) => void;
  signOut: () => Promise<void>;
  isWishlisted: (productId: string) => boolean;
  markWishlisted: (productId: string, wished: boolean) => void;
  toggleWishlist: (productId: string) => Promise<"added" | "removed" | "error" | "auth_required">;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  children,
  initialUser = null,
  initialWishlistCount = 0,
}: {
  children: ReactNode;
  initialUser?: AuthUser | null;
  initialWishlistCount?: number;
}) {
  const [user, setUser] = useState<AuthUser | null>(initialUser);
  const [wishlistCount, setWishlistCount] = useState(initialWishlistCount);
  const [wishlistIds, setWishlistIds] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await fetchAuthMe();
      setUser(payload.user);
      setWishlistCount(payload.wishlist_count);
    } catch {
      setUser(null);
      setWishlistCount(0);
    } finally {
      setLoading(false);
    }
  }, []);

  const setSession = useCallback((next: AuthUser | null, count = 0) => {
    setUser(next);
    setWishlistCount(count);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logoutAccount();
    } finally {
      setUser(null);
      setWishlistCount(0);
      setWishlistIds({});
    }
  }, []);

  const isWishlisted = useCallback(
    (productId: string) => Boolean(wishlistIds[productId]),
    [wishlistIds],
  );

  const markWishlisted = useCallback((productId: string, wished: boolean) => {
    setWishlistIds((current) => ({ ...current, [productId]: wished }));
  }, []);

  const toggleWishlist = useCallback(
    async (productId: string) => {
      if (!user) return "auth_required";
      const wished = Boolean(wishlistIds[productId]);
      try {
        if (wished) {
          const result = await removeWishlistItem(productId);
          setWishlistIds((current) => ({ ...current, [productId]: false }));
          setWishlistCount(result.count);
          return "removed";
        }
        const result = await addWishlistItem(productId);
        setWishlistIds((current) => ({ ...current, [productId]: true }));
        setWishlistCount(result.count);
        return "added";
      } catch {
        return "error";
      }
    },
    [user, wishlistIds],
  );

  const value = useMemo(
    () => ({
      user,
      wishlistCount,
      loading,
      refresh,
      setSession,
      signOut,
      isWishlisted,
      markWishlisted,
      toggleWishlist,
    }),
    [
      user,
      wishlistCount,
      loading,
      refresh,
      setSession,
      signOut,
      isWishlisted,
      markWishlisted,
      toggleWishlist,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

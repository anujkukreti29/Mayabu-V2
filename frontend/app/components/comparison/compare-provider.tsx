import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { productSchema, type Product } from "~/lib/api/schemas";
import { isPublicCategory, PUBLIC_CATEGORY_SLUGS } from "~/lib/search/categories";

const STORAGE_KEY = "mayabu-compare-products";
const MAX_COMPARE_PRODUCTS = 4;

export const COMPARE_SUPPORTED_CATEGORIES = new Set<string>(PUBLIC_CATEGORY_SLUGS);

const storedProductsSchema = productSchema
  .refine((product) => product.title.trim().length > 0)
  .array()
  .max(MAX_COMPARE_PRODUCTS);

export type CompareBlockReason = "unsupported_category" | "category_mismatch" | "full" | null;

interface CompareContextValue {
  products: Product[];
  add: (product: Product) => void;
  remove: (productId: string) => void;
  clear: () => void;
  has: (productId: string) => boolean;
  isFull: boolean;
  maxProducts: number;
  canCompare: (product: Product) => boolean;
  compareBlockReason: (product: Product) => CompareBlockReason;
  activeCategory: string | null;
  /** False until client sessionStorage hydrate completes (SSR-safe). */
  storageReady: boolean;
}

const CompareContext = createContext<CompareContextValue | null>(null);

function readProducts(): Product[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed: unknown = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? "[]");
    const result = storedProductsSchema.safeParse(parsed);
    if (result.success) {
      return result.data.filter((product) => isPublicCategory(product.category));
    }
    window.sessionStorage.removeItem(STORAGE_KEY);
    return [];
  } catch {
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    return [];
  }
}

function writeProducts(products: Product[]) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(products));
  } catch {
    /* ignore quota / private mode */
  }
}

export function compareBlockReasonFor(
  product: Product,
  current: Product[],
  maxProducts = MAX_COMPARE_PRODUCTS,
): CompareBlockReason {
  const category = (product.category || "").toLowerCase();
  if (!COMPARE_SUPPORTED_CATEGORIES.has(category) || !isPublicCategory(category)) {
    return "unsupported_category";
  }
  if (current.some((item) => item.id === product.id)) return null;
  if (current.length >= maxProducts) return "full";
  const active = current[0]?.category?.toLowerCase() ?? null;
  if (active && active !== category) return "category_mismatch";
  return null;
}

export function compareBlockMessage(
  reason: CompareBlockReason,
  maxProducts = MAX_COMPARE_PRODUCTS,
) {
  if (reason === "unsupported_category") {
    return "Compare is available for Mayabu’s public product categories.";
  }
  if (reason === "category_mismatch") {
    return "Compare only products from the same category.";
  }
  if (reason === "full") {
    return `You can compare up to ${maxProducts} products at once.`;
  }
  return null;
}

export function CompareProvider({ children }: { children: ReactNode }) {
  // Start empty/not-ready on SSR. useLayoutEffect hydrates before paint so
  // Compare controls are not interactive until sessionStorage is applied.
  const [products, setProducts] = useState<Product[]>([]);
  const [storageReady, setStorageReady] = useState(false);

  useLayoutEffect(() => {
    setProducts(readProducts());
    setStorageReady(true);
  }, []);

  useLayoutEffect(() => {
    if (storageReady) writeProducts(products);
  }, [products, storageReady]);

  const add = useCallback((product: Product) => {
    setProducts((current) => {
      if (compareBlockReasonFor(product, current) !== null) return current;
      if (current.some((item) => item.id === product.id)) return current;
      return [...current, product];
    });
  }, []);

  const remove = useCallback((productId: string) => {
    setProducts((current) => current.filter((product) => product.id !== productId));
  }, []);
  const clear = useCallback(() => setProducts([]), []);
  const has = useCallback(
    (productId: string) => products.some((product) => product.id === productId),
    [products],
  );

  const compareBlockReason = useCallback(
    (product: Product) => compareBlockReasonFor(product, products),
    [products],
  );

  const canCompare = useCallback(
    (product: Product) => {
      if (!storageReady) return false;
      if (products.some((item) => item.id === product.id)) return true;
      return compareBlockReasonFor(product, products) === null;
    },
    [products, storageReady],
  );

  const value = useMemo<CompareContextValue>(
    () => ({
      products,
      add,
      remove,
      clear,
      has,
      isFull: products.length >= MAX_COMPARE_PRODUCTS,
      maxProducts: MAX_COMPARE_PRODUCTS,
      canCompare,
      compareBlockReason,
      activeCategory: products[0]?.category ?? null,
      storageReady,
    }),
    [products, add, remove, clear, has, canCompare, compareBlockReason, storageReady],
  );

  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}

export function useCompare() {
  const value = useContext(CompareContext);
  if (!value) throw new Error("useCompare must be used inside CompareProvider");
  return value;
}

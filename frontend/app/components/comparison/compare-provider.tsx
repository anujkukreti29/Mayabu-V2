import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { productSchema, type Product } from "~/lib/api/schemas";

const STORAGE_KEY = "mayabu-compare-products";
const MAX_COMPARE_PRODUCTS = 4;
const storedProductsSchema = productSchema
  .refine((product) => product.title.trim().length > 0)
  .array()
  .max(MAX_COMPARE_PRODUCTS);

interface CompareContextValue {
  products: Product[];
  add: (product: Product) => void;
  remove: (productId: string) => void;
  clear: () => void;
  has: (productId: string) => boolean;
}

const CompareContext = createContext<CompareContextValue | null>(null);

function readProducts(): Product[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed: unknown = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? "[]");
    const result = storedProductsSchema.safeParse(parsed);
    if (result.success) return result.data;
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Storage may be disabled; comparison still works in memory.
    }
  }
  return [];
}

function writeProducts(products: Product[]): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(products));
  } catch {
    // Private browsing and quota restrictions should not break the page.
  }
}

export function CompareProvider({ children }: { children: ReactNode }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [storageReady, setStorageReady] = useState(false);

  useEffect(() => {
    setProducts(readProducts());
    setStorageReady(true);
  }, []);

  useEffect(() => {
    if (storageReady) writeProducts(products);
  }, [products, storageReady]);

  const add = useCallback((product: Product) => {
    setProducts((current) => {
      if (
        current.length >= MAX_COMPARE_PRODUCTS ||
        current.some((item) => item.id === product.id)
      ) {
        return current;
      }
      return [...current, product];
    });
  }, []);

  const remove = useCallback((productId: string) => {
    setProducts((current) => current.filter((item) => item.id !== productId));
  }, []);
  const clear = useCallback(() => setProducts([]), []);
  const has = useCallback(
    (productId: string) => products.some((item) => item.id === productId),
    [products],
  );

  const value = useMemo<CompareContextValue>(
    () => ({ products, add, remove, clear, has }),
    [products, add, remove, clear, has],
  );
  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}

export function useCompare() {
  const value = useContext(CompareContext);
  if (!value) throw new Error("useCompare must be used inside CompareProvider");
  return value;
}

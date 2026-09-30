import { Heart } from "lucide-react";
import { useNavigate } from "react-router";
import { useAuth } from "~/components/auth/auth-provider";
import { cn } from "~/components/ui/cn";
import { routes } from "~/lib/navigation/routes";

export function WishlistToggleButton({
  productId,
  productTitle,
  className,
  compact = false,
}: {
  productId: string;
  productTitle?: string | null;
  className?: string;
  compact?: boolean;
}) {
  const auth = useAuth();
  const navigate = useNavigate();
  const wished = auth.isWishlisted(productId);
  const label = wished
    ? `Remove ${productTitle || "product"} from wishlist`
    : `Add ${productTitle || "product"} to wishlist`;

  return (
    <button
      type="button"
      aria-pressed={wished}
      aria-label={label}
      title={auth.user ? label : "Sign in to save to wishlist"}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md border border-line bg-white text-ink transition",
        "hover:border-brand-300 hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
        compact ? "h-9 w-9" : "min-h-11 px-4 text-sm font-semibold",
        wished && "border-brand-300 text-brand-700",
        className,
      )}
      onClick={() => {
        void (async () => {
          const result = await auth.toggleWishlist(productId);
          if (result === "auth_required") {
            void navigate(
              `${routes.login}?next=${encodeURIComponent(typeof window !== "undefined" ? window.location.pathname : "/wishlist")}`,
            );
          }
        })();
      }}
    >
      <Heart
        aria-hidden="true"
        className={cn("h-4 w-4", wished && "fill-brand-600 text-brand-700")}
        strokeWidth={1.75}
      />
      {compact ? null : wished ? "Saved" : "Add to wishlist"}
    </button>
  );
}

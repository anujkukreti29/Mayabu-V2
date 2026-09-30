import { Link } from "react-router";
import { homeCategories } from "~/lib/content/homepage";
import { cn } from "~/components/ui/cn";

export function CategoriesMegaMenu({
  onNavigate,
  className,
}: {
  onNavigate?: () => void;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-1 sm:grid-cols-2 sm:gap-x-4 sm:gap-y-1", className)}>
      {homeCategories.map((category) => (
        <Link
          key={category.id}
          to={category.href}
          onClick={onNavigate}
          className={cn(
            "flex min-h-10 items-center gap-2 rounded-md px-2.5 text-sm font-medium text-ink transition",
            "hover:bg-brand-50 active:bg-brand-100/70",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
          )}
        >
          <span>{category.label}</span>
        </Link>
      ))}
    </div>
  );
}

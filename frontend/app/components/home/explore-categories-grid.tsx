import { Link } from "react-router";
import {
  Box,
  Camera,
  Headphones,
  Laptop,
  Smartphone,
  Snowflake,
  Speaker,
  Tv,
  type LucideIcon,
} from "lucide-react";
import { homeCategories, type HomeCategoryIcon } from "~/lib/content/homepage";
import { cn } from "~/components/ui/cn";

const ICONS: Record<HomeCategoryIcon, LucideIcon> = {
  laptop: Laptop,
  smartphone: Smartphone,
  earbuds: Speaker,
  headphones: Headphones,
  tv: Tv,
  camera: Camera,
  washer: Box,
  fridge: Snowflake,
};

const DESCRIPTORS: Record<string, string> = {
  laptop: "Configs & specs across stores",
  smartphone: "Storage, RAM & network variants",
  television: "Size, panel & resolution",
  refrigerator: "Capacity & door types",
  washing_machine: "Load type & capacity",
  tws: "Earbuds with matched prices",
  headphones: "ANC & wired options",
  camera: "Body & kit configurations",
};

export function ExploreCategoriesGrid({
  counts,
}: {
  counts?: Record<string, number>;
}) {
  return (
    <ul className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {homeCategories.map((category) => {
        const Icon = ICONS[category.icon];
        const count = counts?.[category.slug];
        return (
          <li key={category.id}>
            <Link
              to={category.href}
              className={cn(
                "group flex h-full min-h-[7.5rem] flex-col rounded-lg border border-line bg-white p-4",
                "shadow-soft transition duration-snappy",
                "hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-lift",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                "motion-reduce:hover:translate-y-0",
              )}
            >
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-accent-soft text-brand-800">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <span className="mt-3 text-sm font-semibold text-ink">{category.label}</span>
              <span className="mt-1 text-xs text-ink-muted">
                {DESCRIPTORS[category.slug] ?? "Browse public prices"}
              </span>
              <span className="mt-auto pt-3 text-xs font-semibold text-brand-700 group-hover:underline">
                {typeof count === "number" && count > 0
                  ? `View ${count.toLocaleString("en-IN")} products`
                  : "View products"}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

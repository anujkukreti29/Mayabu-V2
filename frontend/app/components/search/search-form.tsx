import { Search } from "lucide-react";
import { Form } from "react-router";
import { Button } from "~/components/ui/button";
import { cn } from "~/components/ui/cn";

export function SearchForm({
  defaultValue = "",
  compact = false,
}: {
  defaultValue?: string;
  compact?: boolean;
}) {
  return (
    <Form
      method="get"
      action="/search"
      role="search"
      className={cn("flex w-full gap-2", !compact && "max-w-3xl")}
    >
      <label className="sr-only" htmlFor={compact ? "nav-search" : "main-search"}>
        Search Mayabu
      </label>
      <div className="relative min-w-0 flex-1">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
        />
        <input
          id={compact ? "nav-search" : "main-search"}
          name="q"
          type="search"
          defaultValue={defaultValue}
          minLength={2}
          maxLength={160}
          autoComplete="off"
          placeholder={
            compact
              ? "Search products or model numbers"
              : "Search a laptop, phone, model number, or specification"
          }
          className={cn(
            "min-h-11 w-full rounded-xl border border-slate-300 bg-white pl-10 pr-3 text-sm text-slate-950 shadow-sm placeholder:text-slate-400 focus:border-brand-500",
            !compact && "min-h-14 rounded-2xl pl-11 text-base",
          )}
        />
      </div>
      <Button type="submit" size={compact ? "md" : "lg"} aria-label="Search Mayabu">
        <Search aria-hidden="true" className="h-4 w-4 sm:hidden" />
        <span className={compact ? "hidden lg:inline" : "hidden sm:inline"}>Search products</span>
      </Button>
    </Form>
  );
}

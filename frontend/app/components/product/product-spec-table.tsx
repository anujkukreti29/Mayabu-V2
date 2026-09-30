import { cn } from "~/components/ui/cn";

export type SpecRow = { key: string; label: string; value: string };

/** Label | value specification rows — not pills. */
export function ProductSpecTable({
  rows,
  className,
  compact = false,
}: {
  rows: SpecRow[];
  className?: string;
  compact?: boolean;
}) {
  if (rows.length === 0) return null;

  return (
    <dl
      className={cn(
        "divide-y divide-line border-y border-line",
        !compact && "sm:grid sm:grid-cols-2 sm:gap-x-8 sm:divide-y-0 sm:border-0",
        compact ? "text-sm" : "text-sm sm:text-[0.9375rem]",
        className,
      )}
    >
      {rows.map((row) => (
        <div
          key={row.key}
          className={cn(
            "grid grid-cols-[minmax(0,0.42fr)_minmax(0,0.58fr)] gap-3",
            compact ? "py-2" : "py-2.5 sm:border-b sm:border-line sm:py-3",
          )}
        >
          <dt className="font-medium text-ink-muted">{row.label}</dt>
          <dd className="font-semibold text-ink">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

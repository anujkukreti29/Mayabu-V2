import type { Product } from "~/lib/api/schemas";
import type { ResolvedCompareRow } from "~/lib/comparison/spec-registry";
import { cn } from "~/components/ui/cn";

function cellValue(value: string | null): string {
  return value && value.trim() ? value : "—";
}

export function CompareSpecTable({
  products,
  rows,
  caption,
  tableId,
}: {
  products: readonly Product[];
  rows: readonly ResolvedCompareRow[];
  caption: string;
  tableId?: string;
}) {
  if (products.length === 0 || rows.length === 0) return null;

  return (
    <div id={tableId} className="overflow-x-auto rounded-md border border-line bg-white">
      <table className="w-full min-w-[36rem] border-collapse text-left">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line bg-slate-50/80">
            <th
              scope="col"
              className="sticky left-0 z-[1] w-36 border-r border-line bg-slate-50 px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-muted sm:w-44"
            >
              Spec
            </th>
            {products.map((product) => (
              <th
                key={product.id}
                scope="col"
                className="min-w-[10.5rem] px-3 py-2.5 text-xs font-semibold text-ink sm:min-w-[12rem]"
              >
                <span className="line-clamp-2">{product.title}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.def.key}
              data-group={row.def.group}
              className={cn("border-t border-line", row.differs && "bg-slate-50/70")}
            >
              <th
                scope="row"
                className={cn(
                  "sticky left-0 z-[1] border-r border-line bg-white px-3 py-2.5 text-sm font-medium text-ink",
                  row.differs && "bg-slate-50 font-semibold",
                )}
              >
                <span className="inline-flex items-center gap-1.5">
                  {row.def.label}
                  {row.differs ? (
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
                      Diff
                    </span>
                  ) : null}
                </span>
              </th>
              {row.values.map((value, index) => (
                <td
                  key={`${row.def.key}-${products[index]?.id ?? index}`}
                  className={cn(
                    "px-3 py-2.5 text-sm text-ink",
                    row.differs && "font-semibold",
                    !value && "text-ink-muted",
                  )}
                >
                  {cellValue(value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

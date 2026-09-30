import { useState } from "react";
import { ProductImage } from "~/components/product/product-image";
import { cn } from "~/components/ui/cn";
import { normalizeProductImageUrl } from "~/lib/media/product-image-url";

export type GalleryImage = {
  url: string;
  is_primary?: boolean;
  source?: string | null;
};

export function ProductImageGallery({
  images,
  title,
  category,
  fallbackSrc,
}: {
  images: GalleryImage[];
  title: string;
  category?: string | null;
  fallbackSrc?: string | null;
}) {
  const cleaned = images
    .map((item) => ({
      ...item,
      url: normalizeProductImageUrl(item.url) ?? "",
    }))
    .filter((item) => item.url);
  const primary =
    cleaned.find((item) => item.is_primary)?.url ||
    cleaned[0]?.url ||
    normalizeProductImageUrl(fallbackSrc) ||
    null;
  const [active, setActive] = useState(primary);
  const current = active || primary;
  const index = Math.max(
    0,
    cleaned.findIndex((item) => item.url === current),
  );

  function selectOffset(delta: number) {
    if (cleaned.length < 2) return;
    const next = (index + delta + cleaned.length) % cleaned.length;
    setActive(cleaned[next]?.url || current);
  }

  if (!current) {
    return (
      <ProductImage
        src={null}
        alt={title}
        category={category}
        priority
        frameClassName="w-full surface"
      />
    );
  }

  return (
    <div className="min-w-0 max-w-full space-y-3">
      <div className="relative min-w-0 max-w-full">
        <ProductImage
          src={current}
          alt={title}
          category={category}
          priority
          frameClassName="w-full max-w-full surface"
        />
        {cleaned.length > 1 ? (
          <div className="mt-2 flex min-w-0 items-center justify-between gap-2">
            <p className="min-w-0 truncate text-xs text-ink-muted">
              Image {index + 1} of {cleaned.length}
            </p>
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                className="rounded border border-line px-2 py-1 text-xs"
                aria-label="Previous image"
                onClick={() => selectOffset(-1)}
              >
                Prev
              </button>
              <button
                type="button"
                className="rounded border border-line px-2 py-1 text-xs"
                aria-label="Next image"
                onClick={() => selectOffset(1)}
              >
                Next
              </button>
            </div>
          </div>
        ) : null}
      </div>
      {cleaned.length > 1 ? (
        <ul
          className="flex min-w-0 max-w-full gap-2 overflow-x-auto pb-1"
          aria-label="Product image gallery"
        >
          {cleaned.slice(0, 10).map((item, thumbIndex) => {
            const selected = item.url === current;
            return (
              <li key={`${item.url}-${thumbIndex}`} className="shrink-0">
                <button
                  type="button"
                  aria-label={`${title} image ${thumbIndex + 1}`}
                  aria-pressed={selected}
                  onClick={() => setActive(item.url)}
                  className={cn(
                    "h-16 w-16 overflow-hidden rounded-md border bg-slate-50 p-1",
                    selected ? "border-brand-600 ring-1 ring-brand-600" : "border-line",
                  )}
                >
                  <ProductImage
                    src={item.url}
                    alt=""
                    category={category}
                    variant="thumb"
                    frameClassName="h-full w-full !aspect-square !rounded-sm"
                  />
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

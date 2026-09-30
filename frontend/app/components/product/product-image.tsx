import { ImageOff } from "lucide-react";
import { useState } from "react";
import { cn } from "~/components/ui/cn";
import { normalizeProductImageUrl } from "~/lib/media/product-image-url";

/** Category-safe frame ratios for detail-sized presentation. */
export function imageAspectClass(category?: string | null): string {
  switch ((category ?? "").toLowerCase()) {
    case "television":
      return "aspect-video";
    case "smartphone":
    case "refrigerator":
    case "washing_machine":
      return "aspect-[3/4]";
    case "tws":
    case "headphones":
      return "aspect-square";
    case "camera":
      return "aspect-[5/4]";
    case "laptop":
    default:
      return "aspect-[4/3]";
  }
}

type ImageVariant = "detail" | "card" | "thumb";

/** Category-aware max scale so phones aren't tiny next to appliances. */
export function imageContainScaleClass(variant: ImageVariant, category?: string | null): string {
  const slug = (category ?? "").toLowerCase();
  if (variant === "thumb") {
    switch (slug) {
      case "smartphone":
      case "tws":
      case "headphones":
        return "max-h-[88%] max-w-[72%]";
      case "refrigerator":
      case "washing_machine":
        return "max-h-[92%] max-w-[78%]";
      case "television":
        return "max-h-[78%] max-w-[94%]";
      default:
        return "max-h-[90%] max-w-[90%]";
    }
  }
  if (variant === "card") {
    switch (slug) {
      case "smartphone":
      case "tws":
      case "headphones":
        return "max-h-[90%] max-w-[70%]";
      case "refrigerator":
      case "washing_machine":
        return "max-h-[94%] max-w-[80%]";
      case "television":
        return "max-h-[82%] max-w-[96%]";
      default:
        return "max-h-[92%] max-w-[92%]";
    }
  }
  switch (slug) {
    case "smartphone":
    case "tws":
    case "headphones":
      return "max-h-[92%] max-w-[68%]";
    case "refrigerator":
    case "washing_machine":
      return "max-h-[94%] max-w-[78%]";
    case "television":
      return "max-h-[84%] max-w-[96%]";
    default:
      return "max-h-[94%] max-w-[94%]";
  }
}

function frameClasses(variant: ImageVariant, category?: string | null): string {
  if (variant === "thumb") {
    return "aspect-[4/3] max-h-full";
  }
  if (variant === "card") {
    return cn(imageAspectClass(category), "max-h-[11rem] sm:max-h-[12rem]");
  }
  // detail
  switch ((category ?? "").toLowerCase()) {
    case "television":
      return "aspect-video max-h-[18rem] sm:max-h-[22rem]";
    case "smartphone":
    case "refrigerator":
    case "washing_machine":
      return "aspect-[3/4] max-h-[22rem] sm:max-h-[26rem] lg:max-h-[28rem]";
    case "tws":
    case "headphones":
      return "aspect-square max-h-[18rem] sm:max-h-[22rem]";
    case "camera":
      return "aspect-[5/4] max-h-[20rem] sm:max-h-[24rem]";
    default:
      return "aspect-[4/3] max-h-[20rem] sm:max-h-[24rem] lg:max-h-[28rem]";
  }
}

export function ProductImage({
  src,
  alt,
  category,
  className,
  frameClassName,
  priority = false,
  variant = "detail",
}: {
  src?: string | null;
  alt: string;
  category?: string | null;
  className?: string;
  frameClassName?: string;
  priority?: boolean;
  variant?: ImageVariant;
}) {
  const [failed, setFailed] = useState(false);
  const resolved = normalizeProductImageUrl(src);
  const aspect = frameClasses(variant, category);
  const padding = variant === "thumb" ? "p-2" : variant === "card" ? "p-3" : "p-4 sm:p-6";

  if (!resolved || failed) {
    return (
      <div
        className={cn(
          "grid place-items-center rounded-md bg-slate-50 text-center text-slate-500",
          padding,
          aspect,
          frameClassName,
          className,
        )}
        role="img"
        aria-label={`${alt} — image unavailable`}
      >
        <div>
          <ImageOff
            aria-hidden="true"
            className={cn(
              "mx-auto mb-1 text-slate-400",
              variant === "thumb" ? "h-5 w-5" : "h-7 w-7",
            )}
          />
          {variant === "thumb" ? null : (
            <p className="text-xs sm:text-sm">Product image unavailable</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center justify-center overflow-hidden rounded-md bg-slate-50",
        padding,
        aspect,
        frameClassName,
      )}
    >
      <img
        src={resolved}
        alt={alt}
        width={640}
        height={480}
        loading={priority ? "eager" : "lazy"}
        fetchPriority={priority ? "high" : "auto"}
        decoding="async"
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
        className={cn(
          "max-h-full max-w-full object-contain object-center",
          imageContainScaleClass(variant, category),
          className,
        )}
      />
    </div>
  );
}

import { ImageOff } from "lucide-react";
import { useState } from "react";
import { cn } from "~/components/ui/cn";

export function ProductImage({
  src,
  alt,
  className,
  priority = false,
}: {
  src?: string | null;
  alt: string;
  className?: string;
  priority?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div
        className={cn(
          "grid aspect-square place-items-center rounded-xl bg-slate-100 text-center text-sm text-slate-500",
          className,
        )}
      >
        <div>
          <ImageOff aria-hidden="true" className="mx-auto mb-2 h-8 w-8" />
          Product image unavailable
        </div>
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      width={640}
      height={640}
      loading={priority ? "eager" : "lazy"}
      fetchPriority={priority ? "high" : "auto"}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={cn("aspect-square w-full rounded-xl bg-white object-contain", className)}
    />
  );
}

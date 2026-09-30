import { Link } from "react-router";
import { cn } from "~/components/ui/cn";
import { routes } from "~/lib/navigation/routes";

type LogoVariant = "on-light" | "on-dark";

/**
 * Official Mayabu lockup (gradient M + wordmark).
 * on-dark: white wordmark for navy/dark surfaces.
 * on-light: navy wordmark for light surfaces.
 * Preserve aspect ratio; never stretch.
 */
export function MayabuLogo({
  variant = "on-dark",
  className,
  priority = false,
}: {
  variant?: LogoVariant;
  className?: string;
  priority?: boolean;
}) {
  const src = variant === "on-light" ? "/brand/mayabu-logo.png" : "/brand/mayabu-logo-on-dark.png";

  return (
    <Link
      to={routes.home}
      className={cn("inline-flex shrink-0 items-center rounded-sm", className)}
      aria-label="Mayabu home"
    >
      <img
        src={src}
        alt="Mayabu"
        width={1024}
        height={1024}
        decoding={priority ? "sync" : "async"}
        fetchPriority={priority ? "high" : "auto"}
        className="h-[2.25rem] w-auto object-contain object-left sm:h-[2.375rem] lg:h-[2.625rem]"
      />
    </Link>
  );
}

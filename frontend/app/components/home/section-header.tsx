import type { ReactNode } from "react";
import { cn } from "~/components/ui/cn";

export function SectionHeader({
  id,
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  id?: string;
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  const titleId = id ? `${id}-title` : undefined;
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-3", className)}>
      <div className="max-w-3xl">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2 id={titleId} className={cn("section-title", eyebrow && "mt-2")}>
          {title}
        </h2>
        {description ? <p className="muted mt-2 text-sm">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function SectionShell({
  id,
  labelledBy,
  children,
  className,
  tone = "default",
}: {
  id?: string;
  labelledBy?: string;
  children: ReactNode;
  className?: string;
  tone?: "default" | "band";
}) {
  return (
    <section
      id={id}
      aria-labelledby={labelledBy}
      className={cn(tone === "band" && "border-y border-line bg-white", className)}
    >
      {children}
    </section>
  );
}

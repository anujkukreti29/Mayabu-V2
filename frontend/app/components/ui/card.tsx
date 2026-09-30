import type { HTMLAttributes } from "react";
import { cn } from "~/components/ui/cn";

export function Card({ className, interactive = false, ...props }: HTMLAttributes<HTMLDivElement> & {
  interactive?: boolean;
}) {
  return (
    <div
      className={cn(interactive ? "interactive-card" : "surface", className)}
      {...props}
    />
  );
}

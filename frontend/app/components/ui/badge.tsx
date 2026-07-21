import type { HTMLAttributes } from "react";
import { cn } from "~/components/ui/cn";

const tones = {
  neutral: "bg-slate-100 text-slate-700",
  primary: "bg-brand-50 text-brand-700",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-800",
  danger: "bg-red-50 text-red-700",
  info: "bg-sky-50 text-sky-700",
} as const;

export function Badge({
  className,
  children,
  tone = "neutral",
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof tones }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold",
        tones[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  );
}

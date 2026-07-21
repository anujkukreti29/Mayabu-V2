import { cn } from "~/components/ui/cn";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cn("animate-pulse rounded-xl bg-slate-200", className)} />
  );
}

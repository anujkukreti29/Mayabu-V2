import type { ReactNode } from "react";
import { Card } from "~/components/ui/card";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <Card className="px-6 py-10 text-center sm:px-10 sm:py-14">
      <div className="mx-auto mb-4 h-10 w-10 rounded-md bg-surface-muted ring-1 ring-line" aria-hidden="true" />
      <h2 className="text-title-md text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-ink-muted">{description}</p>
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </Card>
  );
}

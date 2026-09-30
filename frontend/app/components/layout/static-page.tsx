import type { ReactNode } from "react";

export function StaticPage({
  eyebrow,
  title,
  intro,
  children,
  atmosphere = false,
}: {
  eyebrow?: string;
  title: string;
  intro: string;
  children: ReactNode;
  atmosphere?: boolean;
}) {
  return (
    <main id="main-content">
      <section
        className={
          atmosphere
            ? "border-b border-line marketing-atmosphere"
            : "border-b border-line bg-white"
        }
      >
        <div className="reading-container py-12 sm:py-16 lg:py-20">
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h1 className="mt-3 max-w-3xl page-title">{title}</h1>
          <p className="mt-4 max-w-2xl text-body-lg text-ink-muted">{intro}</p>
        </div>
      </section>
      <div className="reading-container py-10 sm:py-14">{children}</div>
    </main>
  );
}

export function ContentSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-10 max-w-reading">
      <h2 className="text-title-md text-ink">{title}</h2>
      <div className="mt-3 space-y-3 text-base leading-7 text-ink-soft">{children}</div>
    </section>
  );
}

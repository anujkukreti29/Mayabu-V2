import type { ReactNode } from "react";

export function StaticPage({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow?: string;
  title: string;
  intro: string;
  children: ReactNode;
}) {
  return (
    <main id="main-content">
      <section className="border-b border-slate-200 bg-white">
        <div className="page-container py-14 sm:py-20">
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h1 className="mt-3 max-w-4xl text-4xl font-black tracking-tight text-slate-950 sm:text-5xl">
            {title}
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-600">{intro}</p>
        </div>
      </section>
      <div className="page-container py-12 sm:py-16">{children}</div>
    </main>
  );
}

export function ContentSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-10 max-w-4xl">
      <h2 className="text-2xl font-black text-slate-950">{title}</h2>
      <div className="mt-4 space-y-3 text-base leading-7 text-slate-700">{children}</div>
    </section>
  );
}

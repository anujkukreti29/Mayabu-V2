import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Link } from "react-router";
import { Card } from "~/components/ui/card";
import { SearchForm } from "~/components/search/search-form";

export function CategoryLanding({
  eyebrow,
  title,
  intro,
  intents,
  checks,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  intents: string[];
  checks: string[];
}) {
  return (
    <main id="main-content">
      <section className="border-b border-slate-200 bg-white">
        <div className="page-container py-14 sm:py-20">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="mt-3 max-w-4xl text-4xl font-black tracking-tight text-slate-950 sm:text-5xl">
            {title}
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-600">{intro}</p>
          <div className="mt-8">
            <SearchForm />
          </div>
        </div>
      </section>
      <section className="section-space page-container">
        <h2 className="section-title">Popular research starting points</h2>
        <p className="muted mt-3">
          These links submit normal searches to Mayabu's indexed backend. They do not trigger live
          scraping.
        </p>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {intents.map((intent) => (
            <Link
              key={intent}
              to={`/search?q=${encodeURIComponent(intent)}`}
              className="surface hover:border-brand-300 flex min-h-20 items-center justify-between gap-3 p-4 font-bold hover:bg-brand-50"
            >
              {intent}
              <ArrowRight aria-hidden="true" className="h-4 w-4 shrink-0 text-brand-700" />
            </Link>
          ))}
        </div>
      </section>
      <section className="border-y border-slate-200 bg-white">
        <div className="section-space page-container">
          <h2 className="section-title">Compare the details that change the product</h2>
          <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {checks.map((check) => (
              <Card key={check} className="flex gap-3 p-5">
                <CheckCircle2
                  aria-hidden="true"
                  className="mt-0.5 h-5 w-5 shrink-0 text-brand-600"
                />
                <p className="text-sm font-semibold leading-6">{check}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

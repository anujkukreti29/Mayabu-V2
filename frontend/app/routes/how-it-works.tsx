import {
  ArrowRight,
  CheckCircle2,
  GitCompareArrows,
  History,
  Layers3,
  RefreshCw,
  Search,
  ShieldCheck,
  Store,
  XCircle,
} from "lucide-react";
import type { MetaFunction } from "react-router";
import { Link } from "react-router";
import { Reveal } from "~/components/ui/reveal";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";
import { cn } from "~/components/ui/cn";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "How Mayabu Product and Price Comparison Works",
    description:
      "Learn how Mayabu matches products across stores, compares current prices, checks listings, and shows price evidence without selling products.",
    path: "/how-it-works",
  });

const STEPS = [
  {
    n: "01",
    title: "Search a product",
    copy: "Start with a brand, model, or category. Mayabu returns products with clearer identity—not a random pile of similar titles.",
    icon: Search,
  },
  {
    n: "02",
    title: "Match equivalent listings",
    copy: "Listings are aligned by product identity and material configuration so storage, size, and kit differences stay separate.",
    icon: Layers3,
  },
  {
    n: "03",
    title: "Compare store prices",
    copy: "See current listed prices across supported retailers in one place, with freshness context where available.",
    icon: Store,
  },
  {
    n: "04",
    title: "Check evidence & history",
    copy: "Request a live check on known listings, review Price Evidence, and read observed price history—without inventing trends.",
    icon: History,
  },
] as const;

const MATCH_CARDS = [
  {
    title: "Same product",
    tone: "same" as const,
    points: ["Same model identity", "Same storage / capacity", "Same material configuration"],
  },
  {
    title: "Different variant",
    tone: "diff" as const,
    points: ["Different RAM or storage", "Kit vs body-only camera", "Screen size or colourway"],
  },
] as const;

const DOES = [
  "Compare public store listings for matched products",
  "Track observed prices over time",
  "Distinguish exact matches from similar variants",
  "Show freshness when a price was last checked",
] as const;

const DOES_NOT = [
  "Sell products or process checkout",
  "Guarantee stock or delivery terms",
  "Invent reviews or ratings",
  "Claim an all-time low without recorded history",
] as const;

export default function HowItWorks() {
  return (
    <main id="main-content">
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-line marketing-atmosphere">
        <div className="page-container py-14 sm:py-16 lg:py-20">
          <div className="grid items-end gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:gap-14">
            <div>
              <p className="eyebrow">How Mayabu works</p>
              <h1 className="mt-3 max-w-2xl page-title">From search to a price you can trust.</h1>
              <p className="mt-4 max-w-xl text-body-lg text-ink-muted">
                Mayabu finds matching products across supported stores, normalizes them, checks
                prices, and gives you evidence to compare—without Mayabu selling anything.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Link
                  to={routes.search}
                  className="inline-flex min-h-11 min-w-[9.5rem] items-center justify-center rounded-md bg-accent px-4 text-sm font-semibold text-white transition hover:bg-accent-strong active:translate-y-px"
                >
                  Search products
                </Link>
                <Link
                  to={routes.laptops}
                  className="inline-flex min-h-11 items-center justify-center rounded-md border border-line bg-white px-4 text-sm font-semibold text-ink transition hover:border-line-strong hover:bg-surface-muted"
                >
                  Explore categories
                </Link>
              </div>
            </div>
            <Reveal className="surface-elevated hidden p-5 sm:block lg:p-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
                Decision path
              </p>
              <ol className="mt-4 space-y-3">
                {["Search", "Match", "Compare", "Verify"].map((label, i) => (
                  <li key={label} className="flex items-center gap-3 text-sm font-medium text-ink">
                    <span className="grid h-8 w-8 place-items-center rounded-md bg-surface-muted text-xs font-bold text-accent">
                      {i + 1}
                    </span>
                    {label}
                    {i < 3 ? (
                      <ArrowRight className="ml-auto h-4 w-4 text-ink-faint" aria-hidden="true" />
                    ) : null}
                  </li>
                ))}
              </ol>
            </Reveal>
          </div>
        </div>
      </section>

      {/* Process */}
      <section className="border-b border-line bg-white section-space" aria-labelledby="process-title">
        <div className="page-container">
          <Reveal>
            <p className="eyebrow">The flow</p>
            <h2 id="process-title" className="mt-2 section-title">
              Four steps to clearer comparison
            </h2>
            <p className="mt-2 max-w-2xl muted">
              Designed to be read quickly—on desktop as a connected path, on mobile as a timeline.
            </p>
          </Reveal>

          <div className="relative mt-10">
            <div
              className="pointer-events-none absolute left-[1.15rem] top-4 bottom-4 w-px bg-line sm:left-0 sm:right-0 sm:top-8 sm:bottom-auto sm:h-px sm:w-auto"
              aria-hidden="true"
            />
            <ol className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4 lg:gap-5">
              {STEPS.map((step, index) => {
                const Icon = step.icon;
                return (
                  <Reveal key={step.n} as="li" delayMs={index * 60} className="relative">
                    <div className="surface h-full p-5 pt-6">
                      <div className="flex items-center gap-3">
                        <span className="grid h-10 w-10 place-items-center rounded-md bg-accent-soft text-accent">
                          <Icon className="h-5 w-5" aria-hidden="true" />
                        </span>
                        <span className="text-xs font-bold tracking-wide text-ink-faint">{step.n}</span>
                      </div>
                      <h3 className="mt-4 text-title-sm text-ink">{step.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-ink-muted">{step.copy}</p>
                    </div>
                  </Reveal>
                );
              })}
            </ol>
          </div>
        </div>
      </section>

      {/* Matching */}
      <section className="border-b border-line bg-surface-muted/60 section-space" aria-labelledby="match-title">
        <div className="page-container">
          <Reveal className="max-w-2xl">
            <p className="eyebrow">Matching</p>
            <h2 id="match-title" className="mt-2 section-title">
              Mayabu does not match on titles alone
            </h2>
            <p className="mt-2 muted">
              Model identity, storage, size, capacity, and kit differences matter. Similar-looking
              listings can be different products.
            </p>
          </Reveal>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {MATCH_CARDS.map((card) => (
              <Reveal key={card.title} className="surface p-5 sm:p-6">
                <div className="flex items-center gap-2">
                  {card.tone === "same" ? (
                    <CheckCircle2 className="h-5 w-5 text-positive" aria-hidden="true" />
                  ) : (
                    <GitCompareArrows className="h-5 w-5 text-warning" aria-hidden="true" />
                  )}
                  <h3 className="text-title-sm text-ink">{card.title}</h3>
                </div>
                <ul className="mt-4 space-y-2">
                  {card.points.map((point) => (
                    <li key={point} className="flex gap-2 text-sm text-ink-muted">
                      <span
                        className={cn(
                          "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                          card.tone === "same" ? "bg-positive" : "bg-warning",
                        )}
                      />
                      {point}
                    </li>
                  ))}
                </ul>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Check latest price */}
      <section className="border-b border-line bg-white section-space" aria-labelledby="verify-title">
        <div className="page-container grid items-center gap-10 lg:grid-cols-2 lg:gap-14">
          <Reveal>
            <p className="eyebrow">Live checks</p>
            <h2 id="verify-title" className="mt-2 section-title">
              What happens when you click “Check latest price”
            </h2>
            <p className="mt-3 muted">
              You request a check. Mayabu queues a background job for known supported-store listings,
              records successful observations, and updates Price Evidence. If a store cannot be
              refreshed, the previous trustworthy price is preserved.
            </p>
          </Reveal>
          <Reveal className="surface-elevated p-5 sm:p-6">
            <ol className="space-y-4">
              {[
                { icon: RefreshCw, label: "You request a check", detail: "From the product page" },
                {
                  icon: Store,
                  label: "Known listings are checked",
                  detail: "Only supported store URLs already matched",
                },
                {
                  icon: CheckCircle2,
                  label: "Observations update prices",
                  detail: "Successful fetches become recorded evidence",
                },
                {
                  icon: ShieldCheck,
                  label: "Price Evidence refreshes",
                  detail: "Freshness and store outcomes stay visible",
                },
              ].map((row) => {
                const Icon = row.icon;
                return (
                  <li key={row.label} className="flex gap-3">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-surface-muted text-accent">
                      <Icon className="h-4.5 w-4.5 h-4 w-4" aria-hidden="true" />
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-ink">{row.label}</p>
                      <p className="text-sm text-ink-muted">{row.detail}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </Reveal>
        </div>
      </section>

      {/* History */}
      <section className="border-b border-line bg-surface-muted/40 section-space" aria-labelledby="history-title">
        <div className="page-container">
          <Reveal className="max-w-2xl">
            <p className="eyebrow">History</p>
            <h2 id="history-title" className="mt-2 section-title">
              Observed prices over time
            </h2>
            <p className="mt-2 muted">
              Mayabu records price observations when listings are refreshed or verified. Charts show
              what was observed—not a forecast, and not an invented “deal score.”
            </p>
          </Reveal>
          <Reveal className="mt-8 surface overflow-hidden p-5 sm:p-6" aria-hidden="true">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-faint">
              Illustrative only — not live product data
            </p>
            <div className="mt-4 flex h-28 items-end gap-2 sm:h-32">
              {[42, 48, 45, 52, 40, 38, 44, 36, 34, 39, 32, 30].map((h, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-t-sm bg-accent/20"
                  style={{ height: `${h}%` }}
                />
              ))}
            </div>
            <div className="mt-3 flex justify-between text-xs text-ink-faint">
              <span>Earlier observations</span>
              <span>More recent</span>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Trust / limitations */}
      <section className="border-b border-line bg-white section-space" aria-labelledby="trust-title">
        <div className="page-container">
          <Reveal className="max-w-2xl">
            <p className="eyebrow">Transparency</p>
            <h2 id="trust-title" className="mt-2 section-title">
              What Mayabu does—and does not claim
            </h2>
          </Reveal>
          <div className="mt-8 grid gap-4 lg:grid-cols-2">
            <Reveal className="surface p-5 sm:p-6">
              <h3 className="flex items-center gap-2 text-title-sm text-ink">
                <CheckCircle2 className="h-5 w-5 text-positive" aria-hidden="true" />
                Mayabu does
              </h3>
              <ul className="mt-4 space-y-3">
                {DOES.map((item) => (
                  <li key={item} className="text-sm leading-6 text-ink-muted">
                    {item}
                  </li>
                ))}
              </ul>
            </Reveal>
            <Reveal className="surface p-5 sm:p-6">
              <h3 className="flex items-center gap-2 text-title-sm text-ink">
                <XCircle className="h-5 w-5 text-danger" aria-hidden="true" />
                Mayabu does not
              </h3>
              <ul className="mt-4 space-y-3">
                {DOES_NOT.map((item) => (
                  <li key={item} className="text-sm leading-6 text-ink-muted">
                    {item}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="section-space marketing-atmosphere" aria-labelledby="cta-title">
        <div className="page-container">
          <Reveal className="surface-elevated mx-auto max-w-3xl px-6 py-10 text-center sm:px-10 sm:py-12">
            <h2 id="cta-title" className="section-title">
              Ready to compare?
            </h2>
            <p className="mx-auto mt-3 max-w-lg muted">
              Search a product you are considering, or browse a category to see matched offers and
              price evidence.
            </p>
            <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
              <Link
                to={routes.search}
                className="inline-flex min-h-11 items-center justify-center rounded-md bg-accent px-5 text-sm font-semibold text-white transition hover:bg-accent-strong"
              >
                Search products
              </Link>
              <Link
                to={routes.smartphones}
                className="inline-flex min-h-11 items-center justify-center rounded-md border border-line bg-white px-5 text-sm font-semibold text-ink transition hover:bg-surface-muted"
              >
                Browse categories
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </main>
  );
}

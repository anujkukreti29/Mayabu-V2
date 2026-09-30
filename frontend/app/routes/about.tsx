import {
  ArrowDown,
  Eye,
  GitCompareArrows,
  Layers3,
  Scale,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { MetaFunction } from "react-router";
import { Link } from "react-router";
import { Reveal } from "~/components/ui/reveal";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "About Mayabu | Product and Price Intelligence",
    description:
      "Mayabu helps people compare the correct product variants across Indian retailers with clearer prices, freshness, and evidence—without selling products.",
    path: "/about",
  });

const PRINCIPLES = [
  {
    icon: Scale,
    title: "Truth over hype",
    copy: "No invented deal scores, fake reviews, or manufactured urgency. Evidence should be readable.",
  },
  {
    icon: Layers3,
    title: "Variant accuracy",
    copy: "Storage, kit, size, and configuration differences stay visible so a cheap price cannot hide a different product.",
  },
  {
    icon: Eye,
    title: "Freshness matters",
    copy: "When a price was checked should be as clear as the number itself—especially before you buy.",
  },
  {
    icon: GitCompareArrows,
    title: "Transparent comparisons",
    copy: "Side-by-side specs and store offers are factual. Mayabu does not crown a ‘winner’ for you.",
  },
] as const;

const PIPELINE = [
  "Products",
  "Normalize",
  "Compare stores",
  "Track prices",
  "Decision evidence",
] as const;

export default function About() {
  return (
    <main id="main-content">
      <section className="border-b border-line marketing-atmosphere">
        <div className="page-container py-14 sm:py-16 lg:py-20">
          <p className="eyebrow">About Mayabu</p>
          <h1 className="mt-3 max-w-3xl page-title">
            Better product decisions start with clearer evidence.
          </h1>
          <p className="mt-4 max-w-2xl text-body-lg text-ink-muted">
            Mayabu is a product-discovery and price-intelligence service for Indian electronics. We
            organize identity, retailer offers, and observed history so comparison feels calm and
            trustworthy—not like another marketplace.
          </p>
        </div>
      </section>

      <section className="border-b border-line bg-white section-space" aria-labelledby="purpose-title">
        <div className="page-container grid gap-10 lg:grid-cols-3 lg:gap-12">
          <Reveal className="lg:col-span-1">
            <p className="eyebrow">Purpose</p>
            <h2 id="purpose-title" className="mt-2 section-title">
              Why Mayabu exists
            </h2>
          </Reveal>
          <div className="grid gap-6 sm:grid-cols-3 lg:col-span-2">
            {[
              {
                label: "Problem",
                text: "Prices, specs, and listings are fragmented across stores. Similar titles often hide different variants.",
              },
              {
                label: "Mayabu",
                text: "We organize product identity, retailer offers, tracking, and comparison into one evidence-minded experience.",
              },
              {
                label: "Goal",
                text: "Help people decide with clearer evidence—before they leave for a retailer’s checkout.",
              },
            ].map((block) => (
              <Reveal key={block.label} className="surface p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
                  {block.label}
                </p>
                <p className="mt-3 text-sm leading-6 text-ink-muted">{block.text}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-line bg-surface-muted/50 section-space" aria-labelledby="principles-title">
        <div className="page-container">
          <Reveal className="max-w-2xl">
            <p className="eyebrow">Principles</p>
            <h2 id="principles-title" className="mt-2 section-title">
              What guides the product
            </h2>
          </Reveal>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {PRINCIPLES.map((item, i) => {
              const Icon = item.icon;
              return (
                <Reveal
                  key={item.title}
                  delayMs={i * 50}
                  className="interactive-card p-5 sm:p-6"
                >
                  <span className="grid h-10 w-10 place-items-center rounded-md bg-white text-accent ring-1 ring-line">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <h3 className="mt-4 text-title-sm text-ink">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-ink-muted">{item.copy}</p>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      <section className="border-b border-line bg-white section-space" aria-labelledby="system-title">
        <div className="page-container">
          <Reveal className="max-w-2xl">
            <p className="eyebrow">How evidence is built</p>
            <h2 id="system-title" className="mt-2 section-title">
              From products to decision evidence
            </h2>
            <p className="mt-2 muted">
              A consumer-friendly view of Mayabu’s path—not infrastructure documentation.
            </p>
          </Reveal>
          <Reveal className="mt-8 surface-elevated p-5 sm:p-8">
            <ol className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-2">
              {PIPELINE.map((label, index) => (
                <li key={label} className="flex items-center gap-2 sm:flex-col sm:gap-3">
                  <span className="inline-flex min-h-11 items-center rounded-md bg-surface-muted px-4 text-sm font-semibold text-ink">
                    {label}
                  </span>
                  {index < PIPELINE.length - 1 ? (
                    <ArrowDown
                      className="h-4 w-4 shrink-0 text-ink-faint sm:rotate-[-90deg]"
                      aria-hidden="true"
                    />
                  ) : null}
                </li>
              ))}
            </ol>
          </Reveal>
        </div>
      </section>

      <section className="border-b border-line bg-surface-muted/40 section-space" aria-labelledby="trust-title">
        <div className="page-container grid gap-8 lg:grid-cols-[1fr_1.1fr] lg:items-center">
          <Reveal>
            <p className="eyebrow">Trust</p>
            <h2 id="trust-title" className="mt-2 section-title">
              Clear about what Mayabu is
            </h2>
            <ul className="mt-5 space-y-3 text-sm leading-6 text-ink-muted">
              <li className="flex gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                Mayabu does not sell products.
              </li>
              <li className="flex gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                Retailer links open on retailer sites.
              </li>
              <li className="flex gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                Prices can change; freshness is shown where possible.
              </li>
              <li className="flex gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                Checkout terms remain controlled by the retailer.
              </li>
            </ul>
          </Reveal>
          <Reveal className="surface p-6 sm:p-8">
            <Sparkles className="h-6 w-6 text-accent" aria-hidden="true" />
            <p className="mt-4 text-title-sm text-ink">
              Starting with electronics, expanding carefully.
            </p>
            <p className="mt-3 text-sm leading-6 text-ink-muted">
              Mayabu focuses on categories where matching and freshness quality can be proven—laptops,
              smartphones, TVs, appliances, audio, and cameras—before claiming broader coverage.
            </p>
            <Link
              to={routes.howItWorks}
              className="mt-5 inline-flex min-h-11 items-center text-sm font-semibold text-accent hover:text-accent-strong"
            >
              See how Mayabu works →
            </Link>
          </Reveal>
        </div>
      </section>

      <section className="section-space">
        <div className="page-container">
          <Reveal className="mx-auto max-w-2xl text-center">
            <h2 className="section-title">Compare with clearer context</h2>
            <p className="mt-3 muted">
              Start with a search, or read how matching and live checks work.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Link
                to={routes.search}
                className="inline-flex min-h-11 items-center rounded-md bg-accent px-5 text-sm font-semibold text-white hover:bg-accent-strong"
              >
                Search products
              </Link>
              <Link
                to={routes.contact}
                className="inline-flex min-h-11 items-center rounded-md border border-line bg-white px-5 text-sm font-semibold text-ink hover:bg-surface-muted"
              >
                Contact
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </main>
  );
}

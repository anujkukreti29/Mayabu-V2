import {
  ArrowRight,
  CheckCircle2,
  GitCompareArrows,
  History,
  Search,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router";
import type { MetaFunction } from "react-router";
import { SearchForm } from "~/components/search/search-form";
import { Card } from "~/components/ui/card";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Mayabu: Compare Electronics Prices in India",
    description:
      "Compare exact laptop and mobile variants, prices across Amazon, Flipkart, Croma, and Reliance Digital, price history, and verification freshness with Mayabu.",
    path: "/",
  });

const suggestions = [
  "Gaming laptop under ₹70,000",
  "MacBook Air best price",
  "ASUS Vivobook 14 Ultra 5",
  "Best phone under ₹30,000",
];
const steps = [
  [
    Search,
    "Search the product",
    "Use a product name, model number, or the specifications you need.",
  ],
  [
    CheckCircle2,
    "Confirm the exact variant",
    "Mayabu separates exact matches, similar variants, and related alternatives.",
  ],
  [
    GitCompareArrows,
    "Compare platform offers",
    "Review the best known price, availability, and freshness across supported retailers.",
  ],
  [History, "Check price history", "Understand how the recorded price has moved over time."],
  [
    ShieldCheck,
    "Verify before buying",
    "Request a recent background check for a known store listing without blocking the page.",
  ],
] as const;

export default function Home() {
  return (
    <main id="main-content">
      <section className="overflow-hidden border-b border-slate-200 bg-white">
        <div className="page-container py-16 sm:py-24">
          <p className="eyebrow">Compare smarter. Buy better.</p>
          <h1 className="mt-4 max-w-4xl text-4xl font-black leading-tight tracking-tight text-slate-950 sm:text-6xl">
            Find the best place to buy electronics in India
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-600">
            Compare exact product variants, prices across trusted platforms, price history, and
            verification freshness before you buy.
          </p>
          <div className="mt-8">
            <SearchForm />
          </div>
          <p className="mt-3 text-sm text-slate-500">
            Try a model name, SKU, processor, RAM, storage, or a natural-language query.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {suggestions.map((item) => (
              <Link
                key={item}
                to={`/search?q=${encodeURIComponent(item)}`}
                className="hover:border-brand-300 inline-flex min-h-11 items-center rounded-full border border-slate-200 bg-slate-50 px-4 text-sm font-semibold text-slate-700 hover:bg-brand-50"
              >
                {item}
              </Link>
            ))}
          </div>
          <p className="mt-8 flex items-center gap-2 text-sm font-semibold text-slate-600">
            <ShieldCheck aria-hidden="true" className="h-5 w-5 text-brand-600" />
            Prices from Amazon India, Flipkart, Croma, and Reliance Digital.
          </p>
        </div>
      </section>

      <section className="section-space page-container">
        <p className="eyebrow">Supported retailers</p>
        <h2 className="section-title mt-2">Compare offers from supported Indian retailers</h2>
        <p className="muted mt-3 max-w-3xl">
          Mayabu groups matching listings, keeps material variants separate, and shows when each
          offer was last checked.
        </p>
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {["Amazon India", "Flipkart", "Croma", "Reliance Digital"].map((platform) => (
            <Card
              key={platform}
              className="grid min-h-24 place-items-center p-4 text-center font-black"
            >
              {platform}
            </Card>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white">
        <div className="section-space page-container">
          <p className="eyebrow">Shop by category</p>
          <h2 className="section-title mt-2">Start with the electronics you are researching</h2>
          <div className="mt-7 grid gap-5 md:grid-cols-2">
            <Card className="p-7">
              <h3 className="text-2xl font-black">Laptops</h3>
              <p className="muted mt-3">
                Compare processors, RAM, storage, graphics, displays, model codes, and platform
                prices.
              </p>
              <Link
                to="/laptops"
                className="mt-6 inline-flex min-h-11 items-center gap-2 font-bold text-brand-700"
              >
                Explore laptops
                <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </Link>
            </Card>
            <Card className="p-7">
              <h3 className="text-2xl font-black">Mobile Phones</h3>
              <p className="muted mt-3">
                Compare chipsets, RAM, storage, cameras, batteries, connectivity, variants, and
                offers as backend coverage expands.
              </p>
              <Link
                to="/mobile-phones"
                className="mt-6 inline-flex min-h-11 items-center gap-2 font-bold text-brand-700"
              >
                Explore mobile phones
                <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </Link>
            </Card>
          </div>
        </div>
      </section>

      <section className="section-space page-container">
        <p className="eyebrow">Simple product research</p>
        <h2 className="section-title mt-2">From search to a more confident purchase</h2>
        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          {steps.map(([Icon, title, text], index) => (
            <Card key={title} className="p-5">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-700">
                <Icon aria-hidden="true" className="h-5 w-5" />
              </span>
              <p className="mt-4 text-xs font-bold text-brand-700">Step {index + 1}</p>
              <h3 className="mt-1 font-black">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{text}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white">
        <div className="section-space page-container">
          <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="eyebrow">Transparent freshness</p>
              <h2 className="section-title mt-2">Freshness you can understand</h2>
              <p className="muted mt-4">
                Mayabu never presents an old stored price as a guaranteed live price. Every offer
                includes its latest available freshness context.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                [
                  "Exact matches stay separate",
                  "Material differences such as RAM, storage, generation, model suffix, and screen size are not hidden.",
                ],
                [
                  "Cached prices load immediately",
                  "Product pages do not wait for a scraper before showing useful stored data.",
                ],
                [
                  "Verification is optional",
                  "A request checks known listings in the background and may be queued or rate-limited.",
                ],
                [
                  "Seller checkout remains final",
                  "Coupons, stock, delivery eligibility, and final checkout totals can change.",
                ],
              ].map(([title, text]) => (
                <Card key={title} className="p-5">
                  <h3 className="font-black">{title}</h3>
                  <p className="muted mt-2">{text}</p>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="section-space page-container">
        <p className="eyebrow">Questions</p>
        <h2 className="section-title mt-2">What to know before using Mayabu</h2>
        <div className="mt-6 grid gap-3">
          {[
            [
              "Does Mayabu sell products?",
              "No. Mayabu helps users compare product information and external retailer offers. Purchases are completed on the seller's website.",
            ],
            [
              "Are Mayabu prices live?",
              "Mayabu shows the best known stored price and when it was last checked. Verification can request a recent check, but seller prices can still change.",
            ],
            [
              "How does Mayabu avoid mixing different variants?",
              "Mayabu uses backend product identity, model, and specification matching. Exact products, similar variants, and related products are presented separately.",
            ],
            [
              "Which stores does Mayabu support?",
              "Mayabu currently supports Amazon India, Flipkart, Croma, and Reliance Digital.",
            ],
            [
              "Why verify before buying?",
              "Stock, coupons, delivery location, payment offers, and checkout prices may change after Mayabu last recorded an offer.",
            ],
          ].map(([question, answer]) => (
            <details key={question} className="surface group p-5">
              <summary className="cursor-pointer list-none font-black">{question}</summary>
              <p className="muted mt-3">{answer}</p>
            </details>
          ))}
        </div>
      </section>
    </main>
  );
}

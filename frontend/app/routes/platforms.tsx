import type { MetaFunction } from "react-router";
import { Card } from "~/components/ui/card";
import { StaticPage } from "~/components/layout/static-page";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Supported Ecommerce Platforms | Mayabu",
    description:
      "See the Indian ecommerce platforms Mayabu supports for product matching, price comparison, history, and listing verification.",
    path: "/platforms",
  });

export default function Platforms() {
  return (
    <StaticPage
      eyebrow="Retailer coverage"
      title="Supported ecommerce platforms"
      intro="Mayabu currently compares known product listings from Amazon India, Flipkart, Croma, and Reliance Digital."
    >
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {["Amazon India", "Flipkart", "Croma", "Reliance Digital"].map((platform) => (
          <Card key={platform} className="p-6">
            <span className="inline-flex rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
              Supported
            </span>
            <h2 className="mt-4 text-xl font-black">{platform}</h2>
            <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-600">
              <li>Matched listings</li>
              <li>Price observations</li>
              <li>Known-listing verification</li>
            </ul>
          </Card>
        ))}
      </div>
      <div className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-900">
        Mayabu is not the seller. Product availability, delivery, coupons, and checkout totals are
        controlled by each retailer. Public pages do not expose scraper internals, proxy
        information, worker details, or private health data.
      </div>
    </StaticPage>
  );
}

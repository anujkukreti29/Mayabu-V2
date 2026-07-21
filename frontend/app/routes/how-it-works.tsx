import type { MetaFunction } from "react-router";
import { ContentSection, StaticPage } from "~/components/layout/static-page";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "How Mayabu Product and Price Comparison Works",
    description:
      "Learn how Mayabu separates exact products and variants, compares retailer offers, records price history, and verifies known listings.",
    path: "/how-it-works",
  });

export default function HowItWorks() {
  return (
    <StaticPage
      eyebrow="Transparent product intelligence"
      title="How Mayabu helps you compare before buying"
      intro="Mayabu starts with product identity, then adds retailer offers, historical context, and optional verification without making every page view launch a scraper."
    >
      <ContentSection title="Product identity first">
        <p>
          Mayabu identifies the product and material configuration before comparing prices. Model
          codes, processor generation, RAM, storage, screen, GPU, and suffix differences can prevent
          an incorrect exact match.
        </p>
      </ContentSection>
      <ContentSection title="Exact matches and variants stay separate">
        <p>
          Exact matches represent the same product identity and configuration. Similar variants are
          closely related but materially different. Related products are alternatives, not the same
          item.
        </p>
      </ContentSection>
      <ContentSection title="Stored prices load quickly">
        <p>
          Search results come from PostgreSQL-backed indexed data. Product pages show the latest
          valid stored price immediately and do not wait for browser automation.
        </p>
      </ContentSection>
      <ContentSection title="Price history adds context">
        <p>
          Append-only observations show how recorded prices changed. History can reveal a relative
          low or high, but it is not a prediction and does not guarantee a future price.
        </p>
      </ContentSection>
      <ContentSection title="Verification checks known listings">
        <p>
          A user may request a bounded background check for known product-detail URLs. Requests can
          share an existing job, wait in a queue, enter cooldown, be rate-limited, or fail if a
          retailer blocks access.
        </p>
      </ContentSection>
      <ContentSection title="Seller checkout remains final">
        <p>
          Mayabu is not the seller. Stock, location eligibility, coupons, payment offers, delivery
          fees, and checkout totals remain controlled by the retailer.
        </p>
      </ContentSection>
    </StaticPage>
  );
}

import type { MetaFunction } from "react-router";
import { ContentSection, StaticPage } from "~/components/layout/static-page";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "About Mayabu | Product and Price Intelligence",
    description:
      "Mayabu is building a trusted buying assistant for Indian ecommerce, beginning with electronics matching, price comparison, history, and verification freshness.",
    path: "/about",
  });

export default function About() {
  return (
    <StaticPage
      eyebrow="About Mayabu"
      title="Product and price intelligence built around the correct variant"
      intro="Mayabu is a product-discovery and price-intelligence platform designed to help people compare the correct electronics variant before buying."
    >
      <ContentSection title="Our mission">
        <p>
          Make online product research clearer, faster, and more trustworthy by combining product
          identity, retailer offers, price history, and transparent freshness.
        </p>
      </ContentSection>
      <ContentSection title="What Mayabu believes">
        <ul className="list-disc space-y-2 pl-6">
          <li>The correct variant matters more than a misleading cheap price.</li>
          <li>Price freshness should be visible, not hidden.</li>
          <li>Users should understand the evidence behind a buying insight.</li>
          <li>A scraper failure should never become a fake zero price.</li>
          <li>The retailer's checkout remains the final source for purchase terms.</li>
        </ul>
      </ContentSection>
      <ContentSection title="Starting with electronics">
        <p>
          Mayabu currently focuses on laptops and prepares for mobile-phone coverage across Amazon
          India, Flipkart, Croma, and Reliance Digital. Additional electronics categories will be
          added gradually after data quality is proven.
        </p>
      </ContentSection>
    </StaticPage>
  );
}

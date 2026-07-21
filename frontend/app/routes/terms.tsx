import type { MetaFunction } from "react-router";
import { ContentSection, StaticPage } from "~/components/layout/static-page";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Terms of Use | Mayabu",
    description:
      "Read the Mayabu terms covering product information, retailer links, acceptable use, service availability, and disclaimers.",
    path: "/terms",
  });

export default function Terms() {
  return (
    <StaticPage
      eyebrow="Legal"
      title="Terms of Use"
      intro="This launch draft describes the intended terms for using Mayabu and requires legal review before production launch."
    >
      {(
        [
          [
            "Using Mayabu",
            "Use Mayabu lawfully and do not attempt to disrupt, overload, bypass, scrape, or misuse the service or its retailer integrations.",
          ],
          [
            "Product and price information",
            "Mayabu displays stored product information, price observations, and optional verification results. Information may be incomplete, delayed, or changed by retailers.",
          ],
          [
            "External retailer links",
            "Retailer links lead to independent websites. Their listings, policies, availability, and checkout terms control any purchase.",
          ],
          [
            "No purchase contract with Mayabu",
            "Mayabu is not the seller and does not enter the purchase contract between a user and a retailer.",
          ],
          [
            "Acceptable use",
            "Do not abuse verification limits, submit harmful content, probe private administration routes, or attempt to access secrets or other users' information.",
          ],
          [
            "Intellectual property",
            "Mayabu's original software, design, and branding remain protected. Marketplace names and trademarks belong to their owners.",
          ],
          [
            "Service availability",
            "Search, verification, and retailer access may be unavailable, queued, rate-limited, or interrupted.",
          ],
          [
            "Disclaimers",
            "Mayabu does not guarantee the lowest price, live stock, delivery eligibility, coupon availability, or final checkout total.",
          ],
          [
            "Limitation of liability",
            "Any limitation language must be finalized by qualified legal counsel for the launch jurisdiction.",
          ],
          [
            "Changes and contact",
            "Material terms changes should be dated. A verified contact method must be published before launch.",
          ],
        ] as Array<[string, string]>
      ).map(([title, text]) => (
        <ContentSection key={title} title={title}>
          <p>{text}</p>
        </ContentSection>
      ))}
    </StaticPage>
  );
}

import type { MetaFunction } from "react-router";
import { ContentSection, StaticPage } from "~/components/layout/static-page";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Price and Availability Disclaimer | Mayabu",
    description:
      "Understand how Mayabu displays stored prices, historical observations, verification timestamps, and retailer-controlled checkout terms.",
    path: "/disclaimer",
  });

export default function Disclaimer() {
  return (
    <StaticPage
      eyebrow="Legal"
      title="Price and Availability Disclaimer"
      intro="Mayabu displays stored prices, historical observations, and optional listing-verification results. A verification timestamp shows when Mayabu last observed an offer. It does not guarantee that the price, stock, coupon, delivery eligibility, or checkout total will remain unchanged."
    >
      <ContentSection title="Mayabu is not the seller">
        <p>
          Purchases are completed on retailer websites. Retailers control listings, stock,
          fulfilment, returns, warranties, and checkout terms.
        </p>
      </ContentSection>
      <ContentSection title="Prices can vary">
        <p>
          Prices may differ by location, account, membership, payment method, coupon, bank offer,
          delivery address, tax treatment, or timing.
        </p>
      </ContentSection>
      <ContentSection title="Confirm the exact product">
        <p>
          Users should verify the model code, RAM, storage, colour, processor, screen, included
          accessories, warranty, and final checkout amount on the retailer website.
        </p>
      </ContentSection>
      <ContentSection title="Verification has limits">
        <p>
          Automated checks may be queued, blocked, rate-limited, challenged by a captcha, or unable
          to observe account-specific offers. A failed check keeps the last valid known price rather
          than replacing it with zero.
        </p>
      </ContentSection>
    </StaticPage>
  );
}

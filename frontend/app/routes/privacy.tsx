import type { MetaFunction } from "react-router";
import { ContentSection, StaticPage } from "~/components/layout/static-page";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Privacy Policy | Mayabu",
    description:
      "Read how Mayabu handles anonymous browser identifiers, cookies, analytics, retailer links, retention, security, and user choices.",
    path: "/privacy",
  });

export default function Privacy() {
  return (
    <StaticPage
      eyebrow="Legal"
      title="Privacy Policy"
      intro="This launch draft explains the intended Mayabu privacy model and must receive legal review before production launch."
    >
      {(
        [
          [
            "Information Mayabu collects",
            "Mayabu may process search queries, page requests, anonymous client identifiers, operational logs, and information voluntarily submitted through supported forms.",
          ],
          [
            "How Mayabu uses information",
            "Information is used to operate search, protect rate limits, diagnose failures, improve product matching, and respond to legitimate support requests.",
          ],
          [
            "Anonymous browser identifiers",
            "A random browser identifier may be stored to support fair verification limits and shared-job coordination. It is not designed to identify a person.",
          ],
          [
            "Cookies and local storage",
            "Mayabu may use essential browser storage for comparison state, verification task continuity, preferences, and authenticated sessions when those features exist.",
          ],
          [
            "Analytics",
            "Analytics remain disabled unless enabled through a privacy-aware configuration and any required consent controls.",
          ],
          [
            "Account information",
            "Account data is collected only after authentication and account features are implemented and protected by the backend.",
          ],
          [
            "Data retention",
            "Operational and verification records should be retained only for documented service, security, and legal needs.",
          ],
          [
            "Third-party retailer links",
            "Retailer websites have their own privacy practices. Opening a seller link leaves Mayabu.",
          ],
          [
            "Security",
            "Mayabu limits browser-exposed configuration, validates external links, and keeps database, Redis, scraper, and admin credentials out of frontend code.",
          ],
          [
            "User choices and rights",
            "Users may contact Mayabu about privacy requests after a verified support channel is enabled.",
          ],
          [
            "Important proxy statement",
            "Mayabu does not use a user's device or internet connection as a scraping proxy.",
          ],
          [
            "Policy changes",
            "Material changes should be dated and communicated through this page.",
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

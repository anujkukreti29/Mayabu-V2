import type { MetaFunction } from "react-router";
import { FeatureUnavailable } from "~/components/layout/feature-unavailable";
import { env } from "~/lib/config/env";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Electronics Deals | Mayabu",
    description:
      "Mayabu will show verified price drops after the backend provides trustworthy historical-low and price-change data.",
    path: "/deals",
    robots: env.features.deals ? "index, follow" : "noindex, follow",
  });
export default function Deals() {
  return (
    <FeatureUnavailable
      title="Verified deals are coming soon"
      description="Mayabu will enable this page only after the backend can provide trustworthy price-drop and historical-low data. No deals are fabricated from MRP labels."
    />
  );
}

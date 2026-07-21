import type { MetaFunction } from "react-router";
import { FeatureUnavailable } from "~/components/layout/feature-unavailable";
import { pageMeta } from "~/lib/seo/metadata";
export const meta: MetaFunction = () =>
  pageMeta({
    title: "Price Tracker | Mayabu",
    description:
      "Mayabu price tracking will be available after saved products, alerts, target prices, and authentication are supported by the backend.",
    path: "/tracker",
    robots: "noindex, follow",
  });
export default function Tracker() {
  return (
    <FeatureUnavailable
      title="Track a better price"
      description="Price tracking remains disabled until the backend supports accounts, saved products, target prices, and alert delivery. Mayabu will not simulate alerts in the browser."
    />
  );
}

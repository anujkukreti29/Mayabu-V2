import type { MetaFunction } from "react-router";
import { FeatureUnavailable } from "~/components/layout/feature-unavailable";
import { pageMeta } from "~/lib/seo/metadata";
export const meta: MetaFunction = () =>
  pageMeta({
    title: "My Account | Mayabu",
    description:
      "Mayabu account pages are private and unavailable until backend authentication exists.",
    path: "/account",
    robots: "noindex, nofollow",
  });
export default function Account() {
  return (
    <FeatureUnavailable
      title="Account features are disabled"
      description="Saved products, alerts, history, and settings will appear only after the backend supports authenticated accounts and authorization."
    />
  );
}

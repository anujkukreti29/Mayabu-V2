import type { MetaFunction } from "react-router";
import { FeatureUnavailable } from "~/components/layout/feature-unavailable";
import { pageMeta } from "~/lib/seo/metadata";
export const meta: MetaFunction = () =>
  pageMeta({
    title: "Mayabu Assistant",
    description:
      "The Mayabu assistant will be enabled only after a real backend recommendation endpoint exists.",
    path: "/assistant",
    robots: "noindex, nofollow",
  });
export default function Assistant() {
  return (
    <FeatureUnavailable
      title="The Mayabu assistant is not enabled"
      description="Mayabu will not display a fake chatbot or fabricate products, prices, sellers, specifications, or recommendations without a real backend endpoint."
    />
  );
}

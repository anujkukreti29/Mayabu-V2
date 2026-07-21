import type { MetaFunction } from "react-router";
import { FeatureUnavailable } from "~/components/layout/feature-unavailable";
import { pageMeta } from "~/lib/seo/metadata";
export const meta: MetaFunction = () =>
  pageMeta({
    title: "Administration | Mayabu",
    description: "Mayabu administration is private.",
    path: "/admin",
    robots: "noindex, nofollow",
  });
export default function Admin() {
  return (
    <FeatureUnavailable
      title="Administration is not available in the public frontend"
      description="Admin pages require explicit backend authorization and must never embed an admin token in browser code."
    />
  );
}

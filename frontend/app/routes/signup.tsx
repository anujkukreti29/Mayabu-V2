import type { MetaFunction } from "react-router";
import { FeatureUnavailable } from "~/components/layout/feature-unavailable";
import { pageMeta } from "~/lib/seo/metadata";
export const meta: MetaFunction = () =>
  pageMeta({
    title: "Account Access | Mayabu",
    description:
      "Mayabu account access is disabled until secure backend authentication is available.",
    path: "/login",
    robots: "noindex, nofollow",
  });
export default function Auth() {
  return (
    <FeatureUnavailable
      title="Account access is not enabled"
      description="Authentication remains feature-flagged until the backend provides secure HTTP-only cookie sessions, authorization, and CSRF protection."
    />
  );
}

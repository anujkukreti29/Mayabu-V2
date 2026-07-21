import { data, Link } from "react-router";
import type { MetaFunction } from "react-router";
import { pageMeta } from "~/lib/seo/metadata";
export function loader() {
  return data(null, { status: 404 });
}
export const meta: MetaFunction = () =>
  pageMeta({
    title: "Page Not Found | Mayabu",
    description: "The requested Mayabu page could not be found.",
    path: "/404",
    robots: "noindex, nofollow",
  });
export default function NotFound() {
  return (
    <main id="main-content" className="page-container py-20">
      <h1 className="text-4xl font-black">Page not found</h1>
      <p className="mt-3 text-slate-600">
        The page may have moved, or the product may no longer be available in Mayabu's index.
      </p>
      <Link
        to="/search"
        className="mt-6 inline-flex min-h-11 items-center rounded-xl bg-brand-600 px-5 font-bold text-white"
      >
        Search products
      </Link>
    </main>
  );
}

import { Link } from "react-router";
import { EmptyState } from "~/components/ui/empty-state";

export function FeatureUnavailable({ title, description }: { title: string; description: string }) {
  return (
    <main id="main-content" className="page-container py-16">
      <EmptyState
        title={title}
        description={description}
        action={
          <Link
            to="/search"
            className="inline-flex min-h-11 items-center rounded-xl bg-brand-600 px-5 text-sm font-bold text-white"
          >
            Search products
          </Link>
        }
      />
    </main>
  );
}

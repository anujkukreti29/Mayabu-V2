import { useNavigation } from "react-router";

/** Thin pending indicator — keep previous results visible (dimmed by parent). */
export function SearchPendingBar() {
  const navigation = useNavigation();
  const pending = navigation.state === "loading" && navigation.location?.pathname === "/search";

  if (!pending) return null;

  return (
    <div className="mt-4" aria-live="polite" aria-busy="true">
      <p className="sr-only">Loading search results</p>
      <div className="h-0.5 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full w-1/3 rounded-full bg-brand-500 motion-safe:animate-pulse motion-reduce:w-full" />
      </div>
    </div>
  );
}

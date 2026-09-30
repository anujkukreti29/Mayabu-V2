import type { LinksFunction, LoaderFunctionArgs, MetaFunction } from "react-router";
import {
  isRouteErrorResponse,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useLoaderData,
  useRouteError,
} from "react-router";
import { AppShell } from "~/components/layout/app-shell";
import { useRoutePendingSkeleton } from "~/components/layout/route-pending-skeleton";
import { QueryProvider } from "~/components/layout/query-provider";
import { CompareProvider } from "~/components/comparison/compare-provider";
import { CompareDock, CompareDockSpacer } from "~/components/comparison/compare-dock";
import { AuthProvider } from "~/components/auth/auth-provider";
import { authUserSchema, type AuthUser } from "~/lib/api/auth";
import { resolveApiBaseUrl, env } from "~/lib/config/env";
import stylesheet from "~/styles/app.css?url";

export const links: LinksFunction = () => [
  { rel: "stylesheet", href: stylesheet },
  { rel: "icon", href: "/favicon.svg", type: "image/svg+xml" },
  { rel: "preconnect", href: env.apiBaseUrl },
];

export const meta: MetaFunction = () => [
  { title: "Mayabu — Compare Prices Across Stores & Platforms" },
  {
    name: "description",
    content:
      "Search once and compare product variants and retailer offers across stores in India with Mayabu.",
  },
  { name: "viewport", content: "width=device-width, initial-scale=1" },
  { name: "theme-color", content: "#0b1220" },
];

export function headers() {
  const apiOrigin = new URL(env.apiBaseUrl || "http://127.0.0.1:8000").origin;
  const headers: Record<string, string> = {
    "Content-Security-Policy": `default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data: https:; connect-src 'self' ${apiOrigin}; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline';`,
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    // Root SSR may hydrate auth/wishlist — never share across users/CDN.
    "Cache-Control": "private, no-store",
    Vary: "Cookie",
  };
  if (env.appEnv !== "production") {
    headers["X-Robots-Tag"] = "noindex, nofollow";
  }
  if (env.appEnv === "production") {
    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains";
  }
  return headers;
}

export async function loader({ request }: LoaderFunctionArgs) {
  const cookie = request.headers.get("cookie") || "";
  if (!cookie.includes("mayabu_session=") && !cookie.includes("mayabu_csrf=")) {
    return { user: null as AuthUser | null, wishlistCount: 0 };
  }
  try {
    const response = await fetch(`${resolveApiBaseUrl()}/api/auth/me`, {
      headers: {
        Accept: "application/json",
        Cookie: cookie,
      },
      signal: AbortSignal.timeout(8_000),
    });
    if (!response.ok) return { user: null as AuthUser | null, wishlistCount: 0 };
    const payload = (await response.json()) as {
      user: unknown;
      wishlist_count?: number;
    };
    const parsed = payload.user ? authUserSchema.safeParse(payload.user) : null;
    return {
      user: parsed?.success ? parsed.data : null,
      wishlistCount: Number(payload.wishlist_count || 0),
    };
  } catch {
    return { user: null as AuthUser | null, wishlistCount: 0 };
  }
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN">
      <head>
        <meta charSet="utf-8" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

function AppShellOutlet() {
  const pending = useRoutePendingSkeleton();
  return pending ?? <Outlet />;
}

export default function App() {
  const data = useLoaderData<typeof loader>();
  return (
    <QueryProvider>
      <AuthProvider initialUser={data.user} initialWishlistCount={data.wishlistCount}>
        <CompareProvider>
          <AppShell>
            <AppShellOutlet />
            <CompareDockSpacer />
          </AppShell>
          <CompareDock />
        </CompareProvider>
      </AuthProvider>
    </QueryProvider>
  );
}

export function ErrorBoundary() {
  const error = useRouteError();
  const status = isRouteErrorResponse(error) ? error.status : 500;
  const title = status === 404 ? "Page not found" : "Something went wrong";
  const message =
    status === 404
      ? "The page may have moved, or the product may no longer be available in Mayabu's index."
      : "Mayabu could not load this page. Please try again.";
  return (
    <QueryProvider>
      <AuthProvider initialUser={null} initialWishlistCount={0}>
        <CompareProvider>
          <AppShell>
            <title>{status === 404 ? "Page Not Found | Mayabu" : "Mayabu Service Error"}</title>
            <meta name="robots" content="noindex, nofollow" />
            <main id="main-content" className="page-container py-20">
              <div className="surface mx-auto max-w-2xl p-8 text-center">
                <p className="text-sm font-bold text-brand-700">Error {status}</p>
                <h1 className="mt-2 text-3xl font-black">{title}</h1>
                <p className="mt-3 text-slate-600">{message}</p>
                <a
                  href="/search"
                  className="mt-6 inline-flex min-h-11 items-center rounded-xl bg-brand-600 px-5 font-bold text-white"
                >
                  Search products
                </a>
              </div>
            </main>
          </AppShell>
        </CompareProvider>
      </AuthProvider>
    </QueryProvider>
  );
}

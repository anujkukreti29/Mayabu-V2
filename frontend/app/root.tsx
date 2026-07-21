import type { LinksFunction, MetaFunction } from "react-router";
import {
  isRouteErrorResponse,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useRouteError,
} from "react-router";
import { AppShell } from "~/components/layout/app-shell";
import { QueryProvider } from "~/components/layout/query-provider";
import { CompareProvider } from "~/components/comparison/compare-provider";
import { CompareDock } from "~/components/comparison/compare-dock";
import stylesheet from "~/styles/app.css?url";
import { env } from "~/lib/config/env";

export const links: LinksFunction = () => [
  { rel: "stylesheet", href: stylesheet },
  { rel: "icon", href: "/favicon.svg", type: "image/svg+xml" },
  { rel: "preconnect", href: env.apiBaseUrl },
];

export const meta: MetaFunction = () => [
  { title: "Mayabu: Compare Electronics Prices in India" },
  {
    name: "description",
    content:
      "Compare exact electronics variants, retailer offers, price history, and verification freshness with Mayabu.",
  },
  { name: "viewport", content: "width=device-width, initial-scale=1" },
  { name: "theme-color", content: "#4338ca" },
];

export function headers() {
  const apiOrigin = new URL(env.apiBaseUrl).origin;
  return {
    "Content-Security-Policy": `default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data: https:; connect-src 'self' ${apiOrigin}; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline';`,
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  };
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

export default function App() {
  return (
    <QueryProvider>
      <CompareProvider>
        <AppShell>
          <Outlet />
        </AppShell>
        <CompareDock />
      </CompareProvider>
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
  );
}

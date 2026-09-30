import { Link } from "react-router";
import { MayabuLogo } from "~/components/layout/mayabu-logo";
import { env } from "~/lib/config/env";
import { footerNavigation, routes } from "~/lib/navigation/routes";
import { priceDisclaimer, supportedPlatformsText, trademarkStatement } from "~/lib/content/trust";

const columns = footerNavigation(env.features);

export function Footer() {
  return (
    <footer className="mt-16 border-t border-white/10 bg-header text-slate-300">
      <div className="page-container py-12 lg:py-14">
        <div className="grid gap-10 lg:grid-cols-[1.2fr_2fr] lg:gap-14">
          <div>
            <MayabuLogo variant="on-dark" />
            <p className="mt-5 text-base font-semibold text-white">
              Compare products. Check prices. Decide with evidence.
            </p>
            <p className="mt-3 max-w-md text-sm leading-6 text-slate-400">
              Mayabu organizes product identity, retailer offers, and observed price history so you
              can compare with clearer context—without Mayabu selling the product.
            </p>
            <p className="mt-4 text-sm text-slate-400">
              Currently comparing: {supportedPlatformsText}.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
            {columns.map((column) => (
              <div key={column.title}>
                <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  {column.title}
                </h2>
                <ul className="mt-3 space-y-0.5 text-sm">
                  {column.links.map((link) => (
                    <li key={link.to}>
                      <Link
                        className="inline-flex min-h-10 items-center text-slate-300 transition hover:text-white"
                        to={link.to}
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-10 flex flex-col gap-3 border-t border-white/10 pt-6 text-xs leading-5 text-slate-500 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-3xl space-y-2">
            <p>{priceDisclaimer}</p>
            <p>{trademarkStatement}</p>
          </div>
          <p className="shrink-0 sm:text-right">
            © {new Date().getFullYear()} Mayabu
            <span className="mx-2 text-slate-600">·</span>
            <Link to={routes.about} className="hover:text-white">
              About
            </Link>
          </p>
        </div>
      </div>
    </footer>
  );
}

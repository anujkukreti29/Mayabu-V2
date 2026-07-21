import { Link } from "react-router";
import { env } from "~/lib/config/env";
import { footerNavigation } from "~/lib/navigation/routes";
import { priceDisclaimer, supportedPlatformsText, trademarkStatement } from "~/lib/content/trust";

const columns = footerNavigation(env.features);

export function Footer() {
  return (
    <footer className="mt-20 border-t border-slate-200 bg-slate-950 text-slate-300">
      <div className="page-container py-12">
        <div className="grid gap-10 lg:grid-cols-[1.4fr_2fr]">
          <div>
            <div className="flex items-center gap-2 text-xl font-black text-white">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-500">M</span>
              Mayabu
            </div>
            <p className="mt-3 font-semibold text-white">Compare smarter. Buy better.</p>
            <p className="mt-3 max-w-md text-sm leading-6">
              Search electronics, confirm the exact variant, compare platform offers, review price
              history, and verify a recent price before you buy.
            </p>
            <p className="mt-4 text-sm">Currently supported: {supportedPlatformsText}.</p>
          </div>
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
            {columns.map((column) => (
              <div key={column.title}>
                <h2 className="text-sm font-bold text-white">{column.title}</h2>
                <ul className="mt-3 space-y-2 text-sm">
                  {column.links.map((link) => (
                    <li key={link.to}>
                      <Link
                        className="inline-flex min-h-11 items-center hover:text-white"
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
        <div className="mt-10 border-t border-slate-800 pt-6 text-xs leading-5 text-slate-400">
          <p>{priceDisclaimer}</p>
          <p className="mt-2">{trademarkStatement}</p>
          <p className="mt-2">© {new Date().getFullYear()} Mayabu. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}

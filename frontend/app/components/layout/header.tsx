import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Menu, Search, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useLocation } from "react-router";
import { SearchForm } from "~/components/search/search-form";
import { env } from "~/lib/config/env";
import {
  categoryLinks,
  futureCategories,
  primaryNavigation,
  routes,
} from "~/lib/navigation/routes";
import { sellerStatement } from "~/lib/content/trust";
import { cn } from "~/components/ui/cn";

const publicLinks = primaryNavigation(env.features);

function activeClass({ isActive }: { isActive: boolean }) {
  return cn(
    "inline-flex min-h-11 items-center rounded-lg px-3 text-sm font-semibold text-slate-700 hover:bg-slate-100 hover:text-slate-950",
    isActive && "bg-brand-50 text-brand-700 underline decoration-2 underline-offset-4",
  );
}

export function Header() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="page-container flex min-h-16 items-center gap-3">
        <Link
          to={routes.home}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg font-black text-slate-950"
          aria-label="Mayabu home"
        >
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-600 text-white">
            M
          </span>
          <span className="text-lg">Mayabu</span>
        </Link>
        <div className="hidden min-w-0 max-w-xl flex-1 md:block">
          <SearchForm
            compact
            defaultValue={
              location.pathname === routes.search
                ? (new URLSearchParams(location.search).get("q") ?? "")
                : ""
            }
          />
        </div>
        <nav aria-label="Primary navigation" className="ml-auto hidden items-center xl:flex">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger className="inline-flex min-h-11 items-center gap-1 rounded-lg px-3 text-sm font-semibold text-slate-700 hover:bg-slate-100">
              Categories <ChevronDown aria-hidden="true" className="h-4 w-4" />
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                sideOffset={8}
                className="z-[60] min-w-64 rounded-xl border border-slate-200 bg-white p-2 shadow-xl"
              >
                {categoryLinks.map((link) => (
                  <DropdownMenu.Item key={link.to} asChild>
                    <Link
                      to={link.to}
                      className="block rounded-lg px-3 py-3 text-sm font-semibold outline-none hover:bg-slate-100 focus:bg-slate-100"
                    >
                      {link.label}
                    </Link>
                  </DropdownMenu.Item>
                ))}
                <div className="my-1 border-t border-slate-100" />
                {futureCategories.map((item) => (
                  <div
                    key={item}
                    className="flex items-center justify-between rounded-lg px-3 py-3 text-sm text-slate-500"
                  >
                    {item}
                    <span className="text-xs font-semibold">Coming later</span>
                  </div>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          {publicLinks.map((link) => (
            <NavLink key={link.to} to={link.to} className={activeClass}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <Link
          to={routes.search}
          className="ml-auto grid h-11 w-11 place-items-center rounded-xl border border-slate-300 md:hidden"
          aria-label="Search Mayabu"
        >
          <Search aria-hidden="true" className="h-5 w-5" />
        </Link>
        <Dialog.Root open={open} onOpenChange={setOpen}>
          <Dialog.Trigger asChild>
            <button
              className="grid h-11 w-11 place-items-center rounded-xl border border-slate-300 xl:hidden"
              aria-label={open ? "Close menu" : "Open menu"}
            >
              <Menu aria-hidden="true" className="h-5 w-5" />
            </button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-[70] bg-slate-950/40" />
            <Dialog.Content className="fixed inset-y-0 right-0 z-[80] w-[min(92vw,24rem)] overflow-y-auto bg-white p-5 shadow-2xl focus:outline-none">
              <div className="flex items-center justify-between">
                <div>
                  <Dialog.Title className="text-lg font-black">Mayabu menu</Dialog.Title>
                  <Dialog.Description className="sr-only">
                    Navigate Mayabu categories, product comparison, supported platforms, and trust
                    pages.
                  </Dialog.Description>
                </div>
                <Dialog.Close
                  className="grid h-11 w-11 place-items-center rounded-xl border border-slate-300"
                  aria-label="Close menu"
                >
                  <X aria-hidden="true" className="h-5 w-5" />
                </Dialog.Close>
              </div>
              <div className="mt-5">
                <SearchForm compact />
              </div>
              <nav aria-label="Mobile navigation" className="mt-6 grid gap-1">
                {categoryLinks.map((link) => (
                  <NavLink
                    key={link.to}
                    to={link.to}
                    onClick={() => setOpen(false)}
                    className={activeClass}
                  >
                    {link.label}
                  </NavLink>
                ))}
                {publicLinks.map((link) => (
                  <NavLink
                    key={link.to}
                    to={link.to}
                    onClick={() => setOpen(false)}
                    className={activeClass}
                  >
                    {link.label}
                  </NavLink>
                ))}
              </nav>
              <p className="mt-8 rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-600">
                {sellerStatement} Prices and availability can change on retailer websites.
              </p>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </div>
    </header>
  );
}

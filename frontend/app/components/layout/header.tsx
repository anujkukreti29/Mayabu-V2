import * as Dialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router";
import { CategoriesMegaMenu } from "~/components/layout/categories-mega-menu";
import { CategoriesNavControl } from "~/components/layout/categories-nav-control";
import { HeaderAccountActions } from "~/components/layout/header-account-actions";
import { MayabuLogo } from "~/components/layout/mayabu-logo";
import { SearchForm } from "~/components/search/search-form";
import { env } from "~/lib/config/env";
import { primaryNavigation, routes } from "~/lib/navigation/routes";
import { sellerStatement } from "~/lib/content/trust";
import { cn } from "~/components/ui/cn";

const publicLinks = primaryNavigation(env.features);

function desktopLinkClass({ isActive }: { isActive: boolean }) {
  return cn("nav-link", isActive && "nav-link-active");
}

function mobileLinkClass({ isActive }: { isActive: boolean }) {
  return cn(
    "inline-flex min-h-11 items-center rounded-md px-3 text-sm font-medium text-ink-muted transition hover:bg-surface-muted hover:text-ink",
    isActive && "bg-accent-soft text-accent-strong",
  );
}

export function Header() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();
  const isHome = location.pathname === routes.home;
  const searchDefault =
    location.pathname === routes.search
      ? (new URLSearchParams(location.search).get("q") ?? "")
      : "";

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-nav border-b border-white/10 bg-header text-white transition-[box-shadow,height] duration-smooth",
        scrolled && "shadow-header",
      )}
    >
      <div
        className={cn(
          "page-container flex items-center gap-3 transition-[height] duration-smooth lg:gap-5",
          scrolled ? "h-14 lg:h-[3.75rem]" : "h-14 sm:h-[3.75rem] lg:h-16",
        )}
      >
        <div className="flex shrink-0 items-center border-r border-white/10 pr-3 lg:pr-5">
          <MayabuLogo variant="on-dark" priority className="shrink-0" />
        </div>

        {!isHome ? (
          <div className="hidden min-w-[16rem] max-w-3xl flex-1 lg:block xl:min-w-[22rem]">
            <SearchForm
              compact
              tone="header"
              inputId="nav-search"
              defaultValue={searchDefault}
              key={searchDefault}
            />
          </div>
        ) : (
          <div className="hidden min-w-0 flex-1 lg:block" aria-hidden="true" />
        )}

        <nav
          aria-label="Primary navigation"
          className="ml-auto hidden items-center gap-0.5 lg:flex"
        >
          <CategoriesNavControl />
          {publicLinks.map((link) =>
            link.to.startsWith("/#") ? (
              <a key={link.to} href={link.to} className="nav-link">
                {link.label}
              </a>
            ) : (
              <NavLink key={link.to} to={link.to} className={desktopLinkClass}>
                {link.label}
              </NavLink>
            ),
          )}
        </nav>

        <div className="ml-1 hidden h-6 w-px bg-white/15 sm:block lg:ml-2" aria-hidden="true" />
        <HeaderAccountActions className="hidden sm:flex" />

        <Dialog.Root open={open} onOpenChange={setOpen}>
          <Dialog.Trigger asChild>
            <button
              className="ml-auto grid h-10 w-10 place-items-center rounded-md border border-white/15 text-white transition hover:bg-white/10 lg:hidden"
              aria-label={open ? "Close menu" : "Open menu"}
            >
              <Menu aria-hidden="true" className="h-[1.125rem] w-[1.125rem]" />
            </button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-[70] bg-slate-950/50" />
            <Dialog.Content className="fixed inset-y-0 right-0 z-[80] w-[min(92vw,24rem)] overflow-y-auto bg-white p-5 text-ink shadow-lift focus:outline-none">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <Dialog.Title className="text-base font-semibold">Mayabu menu</Dialog.Title>
                  <Dialog.Description className="sr-only">
                    Navigate Mayabu categories, compare, and account pages.
                  </Dialog.Description>
                </div>
                <Dialog.Close
                  className="grid h-11 w-11 place-items-center rounded-md border border-line"
                  aria-label="Close menu"
                >
                  <X aria-hidden="true" className="h-5 w-5" />
                </Dialog.Close>
              </div>
              <div className="mt-5">
                <SearchForm compact inputId="menu-search" defaultValue={searchDefault} />
              </div>
              <div className="mt-4 flex gap-2 sm:hidden">
                <HeaderAccountActions />
              </div>
              <div className="mt-6 border-t border-line pt-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
                  Categories
                </p>
                <div className="mt-3">
                  <CategoriesMegaMenu
                    onNavigate={() => setOpen(false)}
                    className="sm:grid-cols-1"
                  />
                </div>
              </div>
              <nav
                aria-label="Mobile navigation"
                className="mt-6 grid gap-1 border-t border-line pt-5"
              >
                {publicLinks.map((link) =>
                  link.to.startsWith("/#") ? (
                    <a
                      key={link.to}
                      href={link.to}
                      className={mobileLinkClass({ isActive: false })}
                      onClick={() => setOpen(false)}
                    >
                      {link.label}
                    </a>
                  ) : (
                    <NavLink
                      key={link.to}
                      to={link.to}
                      className={mobileLinkClass}
                      onClick={() => setOpen(false)}
                    >
                      {link.label}
                    </NavLink>
                  ),
                )}
              </nav>
              <p className="mt-8 text-xs leading-5 text-ink-muted">{sellerStatement}</p>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </div>
    </header>
  );
}

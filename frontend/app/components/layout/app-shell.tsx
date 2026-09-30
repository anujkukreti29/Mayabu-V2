import type { ReactNode } from "react";
import { Footer } from "~/components/layout/footer";
import { Header } from "~/components/layout/header";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:left-3 focus-visible:top-3 focus-visible:z-[100] focus-visible:rounded-md focus-visible:bg-header focus-visible:px-4 focus-visible:py-3 focus-visible:text-sm focus-visible:font-semibold focus-visible:text-white"
      >
        Skip to main content
      </a>
      <Header />
      {children}
      <Footer />
    </>
  );
}

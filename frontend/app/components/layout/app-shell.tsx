import type { ReactNode } from "react";
import { Footer } from "~/components/layout/footer";
import { Header } from "~/components/layout/header";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <>
      <a
        href="#main-content"
        className="fixed left-3 top-3 z-[100] -translate-y-24 rounded-lg bg-slate-950 px-4 py-3 font-bold text-white focus:translate-y-0"
      >
        Skip to main content
      </a>
      <Header />
      {children}
      <Footer />
    </>
  );
}

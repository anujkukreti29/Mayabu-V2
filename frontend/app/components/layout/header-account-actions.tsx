import { Heart, UserRound } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Link, useNavigate } from "react-router";
import { useAuth } from "~/components/auth/auth-provider";
import { routes } from "~/lib/navigation/routes";
import { cn } from "~/components/ui/cn";

export function HeaderAccountActions({ className }: { className?: string }) {
  const auth = useAuth();
  const navigate = useNavigate();
  const initial = (auth.user?.display_name || auth.user?.email || "?")
    .trim()
    .charAt(0)
    .toUpperCase();

  return (
    <div className={cn("flex items-center gap-0.5", className)}>
      <button
        type="button"
        aria-label={
          auth.user
            ? auth.wishlistCount > 0
              ? `Wishlist, ${auth.wishlistCount} saved`
              : "Wishlist"
            : "Wishlist, sign in required"
        }
        title="Wishlist"
        className={cn(
          "relative grid h-9 w-9 place-items-center rounded-md text-white/90 transition",
          "hover:bg-white/10 hover:text-white",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40",
        )}
        onClick={() => {
          if (auth.user) void navigate(routes.wishlist);
          else void navigate(`${routes.login}?next=${encodeURIComponent("/wishlist")}`);
        }}
      >
        <Heart aria-hidden="true" className="h-[1.125rem] w-[1.125rem]" strokeWidth={1.75} />
        {auth.user && auth.wishlistCount > 0 ? (
          <span className="absolute right-0.5 top-0.5 grid h-4 min-w-4 place-items-center rounded bg-brand-500 px-1 text-[10px] font-bold leading-none text-white">
            {auth.wishlistCount > 99 ? "99+" : auth.wishlistCount}
          </span>
        ) : null}
      </button>

      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={auth.user ? "Account menu" : "Profile"}
            title={auth.user ? auth.user.display_name || auth.user.email : "Profile"}
            className={cn(
              "grid h-9 w-9 place-items-center rounded-md text-white/90 transition",
              "hover:bg-white/10 hover:text-white",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40",
            )}
          >
            {auth.user ? (
              <span className="grid h-7 w-7 place-items-center rounded-full bg-white/15 text-xs font-bold text-white">
                {initial}
              </span>
            ) : (
              <UserRound
                aria-hidden="true"
                className="h-[1.125rem] w-[1.125rem]"
                strokeWidth={1.75}
              />
            )}
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            sideOffset={10}
            className="z-[70] w-56 rounded-md border border-line bg-white p-2 text-ink shadow-lift"
          >
            {auth.user ? (
              <>
                <DropdownMenu.Label className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  {auth.user.display_name || auth.user.email}
                  {!auth.user.email_verified ? (
                    <span className="mt-1 block font-medium normal-case tracking-normal text-amber-700">
                      Email not verified
                    </span>
                  ) : null}
                </DropdownMenu.Label>
                <DropdownMenu.Item asChild>
                  <Link
                    to={routes.account}
                    className="block cursor-pointer rounded px-2 py-2 text-sm outline-none hover:bg-slate-50"
                  >
                    Account
                  </Link>
                </DropdownMenu.Item>
                <DropdownMenu.Item asChild>
                  <Link
                    to={routes.wishlist}
                    className="block cursor-pointer rounded px-2 py-2 text-sm outline-none hover:bg-slate-50"
                  >
                    Wishlist
                  </Link>
                </DropdownMenu.Item>
                <DropdownMenu.Separator className="my-1 h-px bg-line" />
                <DropdownMenu.Item
                  className="cursor-pointer rounded px-2 py-2 text-sm outline-none hover:bg-slate-50"
                  onSelect={(event) => {
                    // Prevent menu from unmounting before logout finishes clearing session.
                    event.preventDefault();
                    void (async () => {
                      await auth.signOut();
                    })();
                  }}
                >
                  Sign out
                </DropdownMenu.Item>
              </>
            ) : (
              <>
                <DropdownMenu.Item asChild>
                  <Link
                    to={routes.login}
                    className="block cursor-pointer rounded px-2 py-2 text-sm outline-none hover:bg-slate-50"
                  >
                    Sign in
                  </Link>
                </DropdownMenu.Item>
                <DropdownMenu.Item asChild>
                  <Link
                    to={routes.signup}
                    className="block cursor-pointer rounded px-2 py-2 text-sm outline-none hover:bg-slate-50"
                  >
                    Create account
                  </Link>
                </DropdownMenu.Item>
              </>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>
  );
}

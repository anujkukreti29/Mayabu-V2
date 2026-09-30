import { useEffect, useState, type FormEvent } from "react";
import { Link, redirect } from "react-router";
import type { LoaderFunctionArgs, MetaFunction } from "react-router";
import { useAuth } from "~/components/auth/auth-provider";
import { Button } from "~/components/ui/button";
import {
  fetchAuthSessions,
  logoutAllSessions,
  logoutOtherSessions,
  resendVerification,
  revokeAuthSession,
  updateDisplayName,
} from "~/lib/api/auth";
import { ApiError } from "~/lib/api/errors";
import { authErrorMessage, maskEmail } from "~/lib/auth/auth-ux";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";

export function loader({ request }: LoaderFunctionArgs) {
  const cookie = request.headers.get("cookie") || "";
  if (!cookie.includes("mayabu_session=")) {
    const next = encodeURIComponent("/account");
    throw redirect(`/sign-in?next=${next}`);
  }
  return null;
}

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Account | Mayabu",
    description: "Manage your Mayabu account.",
    path: "/account",
    robots: "noindex, follow",
  });

type SessionRow = {
  id: string;
  current: boolean;
  created_at?: string | null;
  last_seen_at?: string | null;
  device_label: string;
};

function formatWhen(value?: string | null) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return "—";
  }
}

export default function AccountPage() {
  const auth = useAuth();
  const [name, setName] = useState(auth.user?.display_name || "");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [resendBusy, setResendBusy] = useState(false);

  useEffect(() => {
    setName(auth.user?.display_name || "");
  }, [auth.user?.display_name]);

  useEffect(() => {
    if (!auth.user) return;
    let cancelled = false;
    setSessionsLoading(true);
    void fetchAuthSessions()
      .then((payload) => {
        if (!cancelled) setSessions(payload.sessions);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load sessions.");
      })
      .finally(() => {
        if (!cancelled) setSessionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.user]);

  if (!auth.user) {
    return (
      <main id="main-content" className="page-container py-16">
        <p className="text-sm text-ink-muted">
          Please{" "}
          <Link to={`${routes.login}?next=/account`} className="font-semibold text-brand-700">
            sign in
          </Link>{" "}
          to view your account.
        </p>
      </main>
    );
  }

  async function onSaveName(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    try {
      const result = await updateDisplayName(name.trim() || null);
      auth.setSession(result.user, auth.wishlistCount);
      setMessage("Display name updated.");
    } catch (err) {
      setError(authErrorMessage(err, "Could not update name."));
    }
  }

  async function onResend() {
    if (resendBusy) return;
    setResendBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await resendVerification();
      setMessage(
        result.status === "queued"
          ? "Verification email sent."
          : result.status === "already_verified"
            ? "Email already verified."
            : "Could not send verification email right now.",
      );
      if (result.status === "already_verified") await auth.refresh();
    } catch (err) {
      setError(authErrorMessage(err, "Could not resend."));
    } finally {
      setResendBusy(false);
    }
  }

  async function refreshSessions() {
    const payload = await fetchAuthSessions();
    setSessions(payload.sessions);
  }

  return (
    <main id="main-content" className="page-container py-10 sm:py-14">
      <div className="border-b border-line pb-6">
        <p className="eyebrow">Your Mayabu account</p>
        <h1 className="mt-2 text-display text-ink">Account</h1>
        <p className="mt-2 text-sm text-ink-muted">Profile, verification, security, and sessions.</p>
      </div>

      <div className="mt-8 grid gap-5 lg:grid-cols-[14rem_1fr]">
        <nav aria-label="Account sections" className="hidden lg:block">
          <ul className="sticky top-24 space-y-1 text-sm">
            {[
              ["profile", "Profile"],
              ["email", "Email"],
              ["security", "Security"],
              ["sessions", "Sessions"],
              ["wishlist", "Wishlist"],
            ].map(([id, label]) => (
              <li key={id}>
                <a
                  href={`#${id}`}
                  className="inline-flex min-h-10 w-full items-center rounded-md px-3 text-ink-muted transition hover:bg-surface-muted hover:text-ink"
                >
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="grid gap-5">
      <section id="profile" className="surface-elevated scroll-mt-28 p-5 sm:p-6">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Profile</h2>
          <form className="mt-4 space-y-3" onSubmit={onSaveName}>
            <label htmlFor="display-name" className="text-sm font-medium text-ink">
              Display name
            </label>
            <input
              id="display-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="nickname"
              className="field-control"
            />
            <Button type="submit">Save name</Button>
          </form>
        </section>

        <section id="email" className="surface-elevated scroll-mt-28 p-5 sm:p-6">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
            Email / verification
          </h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div>
              <dt className="text-ink-muted">Email</dt>
              <dd className="font-medium text-ink">{auth.user.email}</dd>
              <p className="mt-1 text-xs text-ink-muted">
                Email changes require a separate re-verification flow (not available yet).
              </p>
            </div>
            <div>
              <dt className="text-ink-muted">Status</dt>
              <dd>
                {auth.user.email_verified ? (
                  <span className="mt-1 inline-flex min-h-8 items-center rounded-full bg-positive/10 px-2.5 text-sm font-semibold text-positive">
                    Verified
                  </span>
                ) : (
                  <span className="mt-1 inline-block text-sm font-medium text-ink-soft">
                    Email not verified yet
                  </span>
                )}
              </dd>
            </div>
          </dl>
          {!auth.user.email_verified ? (
            <div className="mt-4 space-y-2">
              <p className="text-sm text-ink-muted">
                We can resend a link to {maskEmail(auth.user.email)}.
              </p>
              <Button
                type="button"
                variant="secondary"
                disabled={resendBusy}
                onClick={() => void onResend()}
              >
                {resendBusy ? "Sending…" : "Resend verification"}
              </Button>
            </div>
          ) : null}
        </section>

        <section id="security" className="surface-elevated scroll-mt-28 p-5 sm:p-6">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Security</h2>
          <ul className="mt-4 space-y-2 text-sm text-ink-muted">
            <li>Passwords are hashed with Argon2id.</li>
            <li>
              <Link to={routes.forgotPassword} className="font-medium text-accent hover:text-accent-strong">
                Reset password
              </Link>{" "}
              signs out all devices.
            </li>
            <li>Account deletion is not available in this release.</li>
          </ul>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={() => void auth.signOut()}>
              Sign out
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                void logoutAllSessions()
                  .then(() => auth.setSession(null, 0))
                  .catch(() => setError("Could not sign out all sessions."));
              }}
            >
              Sign out all devices
            </Button>
          </div>
        </section>

        <section id="wishlist" className="surface-elevated scroll-mt-28 p-5 sm:p-6">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Wishlist</h2>
          <p className="mt-4 text-sm text-ink">
            {auth.wishlistCount === 0
              ? "No saved products yet."
              : `${auth.wishlistCount} saved product${auth.wishlistCount === 1 ? "" : "s"}.`}
          </p>
          <Link
            to={routes.wishlist}
            className="mt-4 inline-flex min-h-11 items-center rounded-md border border-line bg-white px-4 text-sm font-semibold text-ink hover:bg-surface-muted"
          >
            Open wishlist
          </Link>
        </section>

        <section id="sessions" className="surface-elevated scroll-mt-28 p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
              Sessions
            </h2>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                void logoutOtherSessions()
                  .then(async (result) => {
                    setMessage(`Signed out ${result.revoked ?? 0} other session(s).`);
                    await refreshSessions();
                  })
                  .catch((err) =>
                    setError(authErrorMessage(err, "Could not revoke other sessions.")),
                  );
              }}
            >
              Sign out other sessions
            </Button>
          </div>
          {sessionsLoading ? (
            <p className="mt-4 text-sm text-ink-muted">Loading sessions…</p>
          ) : sessions.length === 0 ? (
            <p className="mt-4 text-sm text-ink-muted">No active sessions.</p>
          ) : (
            <ul className="mt-4 space-y-2">
              {sessions.map((session) => (
                <li
                  key={session.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-line bg-white px-3 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-ink">
                      {session.device_label}
                      {session.current ? (
                        <span className="ml-2 text-xs font-semibold uppercase tracking-wide text-positive">
                          Current
                        </span>
                      ) : null}
                    </p>
                    <p className="mt-1 text-xs text-ink-muted">
                      Created {formatWhen(session.created_at)} · Last active{" "}
                      {formatWhen(session.last_seen_at)}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      void revokeAuthSession(session.id)
                        .then(async (result) => {
                          if (result.current_revoked) {
                            auth.setSession(null, 0);
                            return;
                          }
                          setMessage("Session signed out.");
                          await refreshSessions();
                        })
                        .catch((err) =>
                          setError(
                            err instanceof ApiError ? err.message : "Could not revoke session.",
                          ),
                        );
                    }}
                  >
                    {session.current ? "Sign out this session" : "Sign out"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {message ? (
          <p className="text-sm text-positive" role="status">
            {message}
          </p>
        ) : null}
        {error ? (
          <p className="text-sm text-danger" role="alert">
            {error}
          </p>
        ) : null}
        </div>
      </div>
    </main>
  );
}

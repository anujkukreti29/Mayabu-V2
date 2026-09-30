import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import type { MetaFunction } from "react-router";
import { AuthCard } from "~/components/auth/auth-form";
import { Button } from "~/components/ui/button";
import { resendVerification, verifyEmailToken } from "~/lib/api/auth";
import { ApiError } from "~/lib/api/errors";
import { authErrorMessage } from "~/lib/auth/auth-ux";
import { useAuth } from "~/components/auth/auth-provider";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";

export const meta: MetaFunction = () => [
  ...pageMeta({
    title: "Verify Email | Mayabu",
    description: "Verify your Mayabu account email address.",
    path: "/verify-email",
    robots: "noindex, follow",
  }),
  { name: "referrer", content: "no-referrer" },
];

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const auth = useAuth();
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "already" | "error">("idle");
  const [message, setMessage] = useState("");
  const [resendState, setResendState] = useState<string | null>(null);
  const [resendBusy, setResendBusy] = useState(false);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("This verification link is missing a token.");
      return;
    }
    let cancelled = false;
    setStatus("loading");
    void verifyEmailToken(token)
      .then(async (result) => {
        if (cancelled) return;
        if (result.status === "already_verified") {
          setStatus("already");
          setMessage("This email is already verified.");
        } else {
          setStatus("ok");
          setMessage("Email verified");
        }
        await auth.refresh();
        if (typeof window !== "undefined") {
          const url = new URL(window.location.href);
          url.searchParams.delete("token");
          window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
        }
      })
      .catch((error) => {
        if (cancelled) return;
        setStatus("error");
        setMessage(error instanceof ApiError ? error.message : "Verification failed.");
      });
    return () => {
      cancelled = true;
    };
    // Intentionally only re-run when token changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function onResend() {
    if (resendBusy) return;
    setResendBusy(true);
    setResendState(null);
    try {
      const result = await resendVerification();
      setResendState(
        result.status === "queued"
          ? "Verification email sent."
          : result.status === "already_verified"
            ? "Already verified."
            : "We could not send email right now. Try again shortly.",
      );
    } catch (error) {
      setResendState(authErrorMessage(error, "Could not resend."));
    } finally {
      setResendBusy(false);
    }
  }

  return (
    <main id="main-content" className="page-container py-12 sm:py-16">
      <AuthCard
        title="Email verification"
        description="Confirm the address on your Mayabu account."
      >
        {status === "loading" ? <p className="text-sm text-ink-muted">Verifying…</p> : null}
        {status === "ok" || status === "already" ? (
          <div className="space-y-4">
            <p className="text-sm font-semibold text-emerald-700" role="status">
              {message}
            </p>
            <Link
              to={routes.home}
              className="inline-flex min-h-11 items-center rounded-md bg-brand-600 px-4 text-sm font-semibold text-white"
            >
              Continue to Mayabu
            </Link>
          </div>
        ) : null}
        {status === "error" ? (
          <div className="space-y-4">
            <p className="text-sm text-rose-600" role="alert">
              {message}
            </p>
            {auth.user ? (
              <Button
                type="button"
                variant="secondary"
                disabled={resendBusy}
                onClick={() => void onResend()}
              >
                {resendBusy ? "Sending…" : "Resend verification"}
              </Button>
            ) : (
              <Link
                to={routes.login}
                className="inline-flex min-h-11 items-center rounded-md border border-line bg-white px-4 text-sm font-semibold text-ink"
              >
                Sign in to resend
              </Link>
            )}
            {resendState ? <p className="text-sm text-ink-muted">{resendState}</p> : null}
          </div>
        ) : null}
      </AuthCard>
    </main>
  );
}

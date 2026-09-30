import { useEffect, useState } from "react";
import { Link } from "react-router";
import type { MetaFunction } from "react-router";
import { AuthCard } from "~/components/auth/auth-form";
import { useAuth } from "~/components/auth/auth-provider";
import { Button } from "~/components/ui/button";
import { resendVerification } from "~/lib/api/auth";
import { authErrorMessage, maskEmail } from "~/lib/auth/auth-ux";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Check Your Email | Mayabu",
    description: "Verify your Mayabu account email address.",
    path: "/check-email",
    robots: "noindex, follow",
  });

export default function CheckEmailPage() {
  const auth = useAuth();
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (cooldownUntil <= Date.now()) return;
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, [cooldownUntil]);

  const cooldownLeft = Math.max(0, Math.ceil((cooldownUntil - now) / 1000));

  if (!auth.user) {
    return (
      <main id="main-content" className="page-container py-12 sm:py-16">
        <AuthCard title="Check your email" description="Sign in to resend a verification link.">
          <Link
            to={routes.login}
            className="inline-flex min-h-11 items-center rounded-md bg-brand-600 px-4 text-sm font-semibold text-white"
          >
            Sign in
          </Link>
        </AuthCard>
      </main>
    );
  }

  if (auth.user.email_verified) {
    return (
      <main id="main-content" className="page-container py-12 sm:py-16">
        <AuthCard title="Email verified" description="Your Mayabu account is ready.">
          <Link
            to={routes.account}
            className="inline-flex min-h-11 items-center rounded-md bg-brand-600 px-4 text-sm font-semibold text-white"
          >
            Continue to Mayabu
          </Link>
        </AuthCard>
      </main>
    );
  }

  async function onResend() {
    if (cooldownLeft > 0 || status === "sending") return;
    setStatus("sending");
    setMessage(null);
    try {
      const result = await resendVerification();
      if (result.status === "already_verified") {
        await auth.refresh();
        setStatus("sent");
        setMessage("Already verified.");
        return;
      }
      if (result.status === "queued") {
        setStatus("sent");
        setMessage("Email sent. Check your inbox.");
      } else {
        setStatus("error");
        setMessage("We could not send email right now. Try again shortly.");
      }
      const retry = result.retry_after_seconds ?? 60;
      setCooldownUntil(Date.now() + retry * 1000);
    } catch (error) {
      setStatus("error");
      setMessage(authErrorMessage(error, "Could not resend verification."));
      setCooldownUntil(Date.now() + 60_000);
    }
  }

  return (
    <main id="main-content" className="page-container py-12 sm:py-16">
      <AuthCard
        title="Check your email"
        description="We sent a verification link to finish setting up your account."
      >
        <p className="text-sm text-ink">
          Sent to <span className="font-semibold">{maskEmail(auth.user.email)}</span>
        </p>
        <p className="mt-3 text-sm leading-6 text-ink-muted">
          You can browse and save products while unverified. Account security features remain
          available after verification.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Button
            type="button"
            onClick={() => void onResend()}
            disabled={status === "sending" || cooldownLeft > 0}
          >
            {status === "sending"
              ? "Sending…"
              : cooldownLeft > 0
                ? `Resend in ${cooldownLeft}s`
                : status === "sent"
                  ? "Email sent"
                  : "Resend email"}
          </Button>
          <Button type="button" variant="secondary" onClick={() => void auth.signOut()}>
            Sign out
          </Button>
          <Link
            to={routes.search}
            className="inline-flex min-h-11 items-center justify-center rounded-md border border-line bg-white px-4 text-sm font-semibold text-ink hover:bg-slate-50"
          >
            Continue browsing
          </Link>
        </div>
        {message ? (
          <p
            className={`mt-4 text-sm ${status === "error" ? "text-rose-600" : "text-emerald-700"}`}
            role={status === "error" ? "alert" : "status"}
          >
            {message}
          </p>
        ) : null}
      </AuthCard>
    </main>
  );
}

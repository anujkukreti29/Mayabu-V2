import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import type { MetaFunction } from "react-router";
import { AuthCard, AuthField } from "~/components/auth/auth-form";
import { Button } from "~/components/ui/button";
import { resetPassword } from "~/lib/api/auth";
import { authErrorMessage } from "~/lib/auth/auth-ux";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";

export const meta: MetaFunction = () => [
  ...pageMeta({
    title: "Reset Password | Mayabu",
    description: "Choose a new Mayabu account password.",
    path: "/reset-password",
    robots: "noindex, follow",
  }),
  { name: "referrer", content: "no-referrer" },
];

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("This reset link is missing a token.");
    }
  }, [token]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (loading || !token) return;
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await resetPassword(token, password);
      setDone(true);
      if (typeof window !== "undefined") {
        const url = new URL(window.location.href);
        url.searchParams.delete("token");
        window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
      }
    } catch (err) {
      setError(authErrorMessage(err, "Could not reset password."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main id="main-content" className="page-container py-12 sm:py-16">
      <AuthCard
        title={done ? "Password updated" : "Reset password"}
        description={
          done
            ? "Existing sessions were signed out for your security."
            : "Choose a new password for your Mayabu account."
        }
        footer={
          <Link to={`${routes.login}?reset=1`} className="font-semibold text-brand-700">
            {done ? "Sign in" : "Back to sign in"}
          </Link>
        }
      >
        {done ? (
          <div className="space-y-4">
            <p className="text-sm text-emerald-700" role="status">
              Your password was changed successfully.
            </p>
            <Link
              to={`${routes.login}?reset=1`}
              className="inline-flex min-h-11 items-center rounded-md bg-brand-600 px-4 text-sm font-semibold text-white"
            >
              Sign in
            </Link>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={onSubmit}>
            <AuthField
              id="password"
              label="New password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={setPassword}
            />
            <AuthField
              id="confirm-password"
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={setConfirm}
            />
            <p className="text-xs text-ink-muted">Use at least 8 characters.</p>
            {error ? (
              <p className="text-sm text-rose-600" role="alert">
                {error}
              </p>
            ) : null}
            <Button type="submit" className="w-full" disabled={loading || !token}>
              {loading ? "Updating…" : "Update password"}
            </Button>
          </form>
        )}
      </AuthCard>
    </main>
  );
}

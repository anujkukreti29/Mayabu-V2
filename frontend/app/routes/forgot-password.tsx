import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import type { MetaFunction } from "react-router";
import { AuthCard, AuthField } from "~/components/auth/auth-form";
import { Button } from "~/components/ui/button";
import { forgotPassword } from "~/lib/api/auth";
import { authErrorMessage } from "~/lib/auth/auth-ux";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Forgot Password | Mayabu",
    description: "Request a Mayabu password reset link.",
    path: "/forgot-password",
    robots: "noindex, follow",
  });

const GENERIC = "If an account exists for that email, we'll send password reset instructions.";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await forgotPassword(email);
      setMessage(GENERIC);
    } catch (err) {
      setError(authErrorMessage(err, "Could not start password reset."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main id="main-content" className="page-container py-12 sm:py-16">
      <AuthCard
        title="Forgot password"
        description="Enter your email and we’ll send reset instructions if an account exists."
        footer={
          <Link to={routes.login} className="font-semibold text-brand-700">
            Back to sign in
          </Link>
        }
      >
        <form className="space-y-4" onSubmit={onSubmit}>
          <AuthField
            id="email"
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={setEmail}
          />
          {error ? (
            <p className="text-sm text-rose-600" role="alert">
              {error}
            </p>
          ) : null}
          {message ? (
            <p className="text-sm text-emerald-700" role="status">
              {message}
            </p>
          ) : null}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      </AuthCard>
    </main>
  );
}

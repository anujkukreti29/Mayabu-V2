import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import type { MetaFunction } from "react-router";
import { AuthCard, AuthField } from "~/components/auth/auth-form";
import { useAuth } from "~/components/auth/auth-provider";
import { Button } from "~/components/ui/button";
import { loginAccount } from "~/lib/api/auth";
import { authErrorMessage } from "~/lib/auth/auth-ux";
import { safeNextPath } from "~/lib/auth/safe-next";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Sign In | Mayabu",
    description: "Sign in to Mayabu to save products to your wishlist.",
    path: "/sign-in",
    robots: "noindex, follow",
  });

export default function SignInPage() {
  const [params] = useSearchParams();
  const next = safeNextPath(params.get("next"), "/account");
  const resetNotice = params.get("reset") === "1";
  const navigate = useNavigate();
  const auth = useAuth();
  const errorId = useId();
  const errorRef = useRef<HTMLParagraphElement>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const result = await loginAccount({ email, password });
      auth.setSession(result.user, auth.wishlistCount);
      await auth.refresh();
      void navigate(next);
    } catch (err) {
      setPassword("");
      setError(authErrorMessage(err, "Invalid email or password."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main id="main-content" className="page-container py-12 sm:py-16">
      <AuthCard
        title="Sign in"
        description="Access your wishlist and account settings."
        footer={
          <>
            New to Mayabu?{" "}
            <Link
              to={`${routes.signup}?next=${encodeURIComponent(next)}`}
              className="font-semibold text-brand-700"
            >
              Create account
            </Link>
          </>
        }
      >
        {resetNotice ? (
          <p
            className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
            role="status"
          >
            Password updated. Sign in with your new password.
          </p>
        ) : null}
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
          <AuthField
            id="password"
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={setPassword}
          />
          {error ? (
            <p
              ref={errorRef}
              id={errorId}
              className="text-sm text-rose-600"
              role="alert"
              tabIndex={-1}
            >
              {error}
            </p>
          ) : null}
          <Button
            type="submit"
            className="w-full"
            disabled={loading}
            aria-describedby={error ? errorId : undefined}
          >
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-sm">
          <Link
            to={routes.forgotPassword}
            className="font-medium text-brand-700 hover:text-brand-800"
          >
            Forgot password?
          </Link>
        </p>
      </AuthCard>
    </main>
  );
}

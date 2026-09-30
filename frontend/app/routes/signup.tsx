import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import type { MetaFunction } from "react-router";
import { AuthCard, AuthField } from "~/components/auth/auth-form";
import { useAuth } from "~/components/auth/auth-provider";
import { Button } from "~/components/ui/button";
import { registerAccount } from "~/lib/api/auth";
import { ApiError } from "~/lib/api/errors";
import { authErrorMessage } from "~/lib/auth/auth-ux";
import { safeNextPath } from "~/lib/auth/safe-next";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Create Account | Mayabu",
    description: "Create a Mayabu account to save products across devices.",
    path: "/signup",
    robots: "noindex, follow",
  });

export default function SignUpPage() {
  const [params] = useSearchParams();
  const next = safeNextPath(params.get("next"), "/account");
  const navigate = useNavigate();
  const auth = useAuth();
  const errorId = useId();
  const errorRef = useRef<HTMLParagraphElement>(null);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    setFieldError(null);
    setError(null);
    if (password !== confirm) {
      setFieldError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setFieldError("Use at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      const result = await registerAccount({
        email,
        password,
        display_name: displayName.trim() || undefined,
      });
      auth.setSession(result.user, 0);
      await auth.refresh();
      void navigate(routes.checkEmail);
    } catch (err) {
      setError(authErrorMessage(err, "Could not create account."));
      if (err instanceof ApiError && err.status === 409) {
        // keep email filled for recovery
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main id="main-content" className="page-container py-12 sm:py-16">
      <AuthCard
        title="Create account"
        description="Save products to your wishlist and pick up where you left off."
        footer={
          <>
            Already have an account?{" "}
            <Link
              to={`${routes.login}?next=${encodeURIComponent(next)}`}
              className="font-semibold text-brand-700"
            >
              Sign in
            </Link>
          </>
        }
      >
        <form className="space-y-4" onSubmit={onSubmit} noValidate>
          <AuthField
            id="name"
            label="Name"
            autoComplete="name"
            value={displayName}
            onChange={setDisplayName}
          />
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
            autoComplete="new-password"
            required
            value={password}
            onChange={setPassword}
            error={fieldError && password !== confirm ? null : fieldError}
          />
          <AuthField
            id="confirm-password"
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={setConfirm}
            error={fieldError && password !== confirm ? fieldError : null}
          />
          <p className="text-xs leading-5 text-ink-muted" id="password-hint">
            Use at least 8 characters. A passphrase works well.
          </p>
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
            aria-describedby={error ? errorId : "password-hint"}
          >
            {loading ? "Creating account…" : "Create account"}
          </Button>
        </form>
      </AuthCard>
    </main>
  );
}

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Button } from "~/components/ui/button";
import { cn } from "~/components/ui/cn";

export function AuthField({
  id,
  label,
  type = "text",
  autoComplete,
  value,
  onChange,
  required,
  error,
}: {
  id: string;
  label: string;
  type?: string;
  autoComplete?: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  error?: string | null;
}) {
  const [show, setShow] = useState(false);
  const isPassword = type === "password";
  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium text-ink">
        {label}
      </label>
      <div className="relative mt-1.5">
        <input
          id={id}
          name={id}
          type={isPassword && show ? "text" : type}
          autoComplete={autoComplete}
          required={required}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className={cn(
            "h-11 w-full rounded-md border border-line bg-white px-3 text-sm text-ink outline-none",
            "transition duration-instant focus-visible:border-accent focus-visible:shadow-focus",
            isPassword && "pr-11",
            error && "border-danger",
          )}
        />
        {isPassword ? (
          <button
            type="button"
            className="absolute inset-y-0 right-0 grid w-11 place-items-center text-ink-muted transition hover:text-ink"
            aria-label={show ? "Hide password" : "Show password"}
            onClick={() => setShow((current) => !current)}
          >
            {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        ) : null}
      </div>
      {error ? (
        <p className="mt-1 text-xs text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function AuthCard({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-md">
      <div className="rounded-lg border border-line bg-white p-6 shadow-soft sm:p-8">
        <p className="eyebrow">Mayabu account</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-ink">{title}</h1>
        {description ? (
          <p className="mt-2 text-sm leading-6 text-ink-muted">{description}</p>
        ) : null}
        <div className="mt-6">{children}</div>
      </div>
      {footer ? <div className="mt-4 text-center text-sm text-ink-muted">{footer}</div> : null}
    </div>
  );
}

export function AuthSubmit({ loading, label }: { loading: boolean; label: string }) {
  return (
    <Button type="submit" className="mt-5 w-full" disabled={loading}>
      {loading ? "Please wait…" : label}
    </Button>
  );
}

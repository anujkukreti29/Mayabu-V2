import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "~/components/ui/cn";

const styles = cva(
  [
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-semibold",
    "transition duration-instant ease-mayabu",
    "focus-visible:outline-none focus-visible:shadow-focus",
    "disabled:cursor-not-allowed disabled:opacity-50",
    "active:translate-y-px motion-reduce:active:translate-y-0",
  ].join(" "),
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-white hover:bg-accent-strong shadow-sm hover:shadow-soft",
        secondary: "bg-ink text-white hover:bg-ink-soft",
        outline:
          "border border-line bg-white text-ink hover:border-line-strong hover:bg-surface-muted",
        ghost: "text-ink-muted hover:bg-surface-muted hover:text-ink",
        danger: "bg-danger text-white hover:bg-red-700",
      },
      size: {
        sm: "min-h-10 px-3 text-[13px]",
        md: "min-h-11 px-4",
        lg: "min-h-12 px-5 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof styles> {}

export function Button({ className, variant, size, type = "button", ...props }: ButtonProps) {
  return <button type={type} className={cn(styles({ variant, size }), className)} {...props} />;
}

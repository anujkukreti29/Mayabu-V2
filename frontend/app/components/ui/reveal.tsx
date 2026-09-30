import {
  useLayoutEffect,
  useRef,
  useState,
  type ElementType,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { cn } from "~/components/ui/cn";

type RevealTag = "div" | "section" | "article" | "li";

/**
 * One-shot viewport entrance. Honors prefers-reduced-motion.
 * SSR keeps content readable; below-fold arms hide only after layout
 * measurement so full-page screenshots and slow IO never leave blank gaps.
 */
export function Reveal({
  children,
  className,
  as = "div",
  delayMs = 0,
  ...rest
}: {
  children: ReactNode;
  className?: string;
  as?: RevealTag;
  delayMs?: number;
} & HTMLAttributes<HTMLElement>) {
  const ref = useRef<HTMLElement | null>(null);
  const [armed, setArmed] = useState(false);
  const [visible, setVisible] = useState(false);
  const Tag = as as ElementType;

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof window === "undefined" || !("IntersectionObserver" in window)) {
      setVisible(true);
      return;
    }

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setVisible(true);
      return;
    }

    const rect = node.getBoundingClientRect();
    const nearViewport =
      rect.top < window.innerHeight * 0.98 && rect.bottom > -64 && rect.height > 0;
    if (nearViewport) {
      setVisible(true);
      return;
    }

    setArmed(true);

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true);
            setArmed(false);
            observer.disconnect();
            break;
          }
        }
      },
      { rootMargin: "16% 0px 16% 0px", threshold: 0.04 },
    );
    observer.observe(node);

    const fallback = window.setTimeout(() => {
      setVisible(true);
      setArmed(false);
      observer.disconnect();
    }, 900);

    return () => {
      observer.disconnect();
      window.clearTimeout(fallback);
    };
  }, []);

  const show = visible || !armed;

  return (
    <Tag
      ref={ref}
      className={cn(show ? "reveal-visible" : "reveal-ready", className)}
      style={delayMs && visible ? { animationDelay: `${delayMs}ms` } : undefined}
      {...rest}
    >
      {children}
    </Tag>
  );
}

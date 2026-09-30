import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { HomeCarouselSlide } from "~/components/home/carousel-types";
import { CarouselSlideView } from "~/components/home/carousel-slide-view";
import { cn } from "~/components/ui/cn";

const ROTATE_MS = 5500;
const MANUAL_RESUME_MS = 8000;

export function PromoCarousel({ slides }: { slides: readonly HomeCarouselSlide[] }) {
  const labelId = useId();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [manualPause, setManualPause] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [progressKey, setProgressKey] = useState(0);
  const regionRef = useRef<HTMLDivElement>(null);
  const touchStartX = useRef<number | null>(null);
  const resumeTimer = useRef<number | null>(null);

  const count = slides.length;
  const active = slides[index] ?? slides[0];

  const clearResumeTimer = () => {
    if (resumeTimer.current != null) {
      window.clearTimeout(resumeTimer.current);
      resumeTimer.current = null;
    }
  };

  const goTo = useCallback(
    (next: number) => {
      if (count === 0) return;
      setIndex(((next % count) + count) % count);
      setProgressKey((value) => value + 1);
    },
    [count],
  );

  const pauseAfterManual = useCallback(() => {
    setManualPause(true);
    clearResumeTimer();
    resumeTimer.current = window.setTimeout(() => {
      setManualPause(false);
      setProgressKey((value) => value + 1);
    }, MANUAL_RESUME_MS);
  }, []);

  const goPrevious = useCallback(() => {
    pauseAfterManual();
    goTo(index - 1);
  }, [goTo, index, pauseAfterManual]);

  const goNext = useCallback(() => {
    pauseAfterManual();
    goTo(index + 1);
  }, [goTo, index, pauseAfterManual]);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReducedMotion(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    const node = regionRef.current;
    if (!node) return;
    const pause = () => setPaused(true);
    const resume = () => setPaused(false);
    const onFocusOut = (event: FocusEvent) => {
      const next = event.relatedTarget;
      if (next instanceof Node && node.contains(next)) return;
      resume();
    };
    node.addEventListener("pointerenter", pause);
    node.addEventListener("pointerleave", resume);
    node.addEventListener("focusin", pause);
    node.addEventListener("focusout", onFocusOut);
    return () => {
      node.removeEventListener("pointerenter", pause);
      node.removeEventListener("pointerleave", resume);
      node.removeEventListener("focusin", pause);
      node.removeEventListener("focusout", onFocusOut);
    };
  }, []);

  useEffect(() => () => clearResumeTimer(), []);

  useEffect(() => {
    if (paused || manualPause || reducedMotion || count < 2) return;
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % count);
      setProgressKey((value) => value + 1);
    }, ROTATE_MS);
    return () => window.clearInterval(timer);
  }, [paused, manualPause, reducedMotion, count]);

  useEffect(() => {
    const node = regionRef.current;
    if (!node) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        goPrevious();
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        goNext();
      } else if (event.key === "Home") {
        event.preventDefault();
        pauseAfterManual();
        goTo(0);
      } else if (event.key === "End") {
        event.preventDefault();
        pauseAfterManual();
        goTo(count - 1);
      }
    };
    node.addEventListener("keydown", onKeyDown);
    return () => node.removeEventListener("keydown", onKeyDown);
  }, [goPrevious, goNext, goTo, count, pauseAfterManual]);

  if (!active) return null;

  return (
    <div
      ref={regionRef}
      role="region"
      aria-roledescription="carousel"
      aria-labelledby={labelId}
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- WAI-ARIA carousel keyboard pattern
      tabIndex={0}
      className="w-full min-w-0 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2"
      onTouchStart={(event) => {
        touchStartX.current = event.changedTouches[0]?.clientX ?? null;
      }}
      onTouchEnd={(event) => {
        const start = touchStartX.current;
        const end = event.changedTouches[0]?.clientX;
        touchStartX.current = null;
        if (start == null || end == null) return;
        const delta = end - start;
        if (Math.abs(delta) < 48) return;
        if (delta < 0) goNext();
        else goPrevious();
      }}
    >
      <p id={labelId} className="sr-only">
        Mayabu homepage highlights
      </p>

      <div className="overflow-hidden rounded-md border border-line bg-white shadow-soft">
        <div className="relative min-h-[22rem] min-w-0 sm:min-h-[24rem] lg:min-h-[26rem]">
          {slides.map((slide, slideIndex) => (
            <CarouselSlideView
              key={slide.id}
              slide={slide}
              active={slideIndex === index}
              labelledBy={`${labelId}-slide-${slide.id}`}
            />
          ))}
        </div>

        <div className="border-t border-line bg-slate-50/80 px-3 py-2.5 sm:px-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                aria-label="Previous slide"
                onClick={goPrevious}
                className="grid h-10 w-10 place-items-center rounded-md border border-line bg-white text-ink transition hover:border-brand-300 hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 active:scale-[0.97] motion-reduce:active:scale-100"
              >
                <ChevronLeft aria-hidden="true" className="h-5 w-5" />
              </button>
              <button
                type="button"
                aria-label="Next slide"
                onClick={goNext}
                className="grid h-10 w-10 place-items-center rounded-md border border-line bg-white text-ink transition hover:border-brand-300 hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 active:scale-[0.97] motion-reduce:active:scale-100"
              >
                <ChevronRight aria-hidden="true" className="h-5 w-5" />
              </button>
            </div>

            <div
              className="flex flex-1 flex-wrap items-center gap-1.5"
              aria-label="Carousel slides"
            >
              {slides.map((slide, slideIndex) => {
                const activeSlide = slideIndex === index;
                return (
                  <button
                    key={slide.id}
                    type="button"
                    aria-label={`Go to slide ${slideIndex + 1}`}
                    aria-current={activeSlide ? "true" : undefined}
                    onClick={() => {
                      pauseAfterManual();
                      goTo(slideIndex);
                    }}
                    className={cn(
                      "relative h-1.5 overflow-hidden rounded-sm transition-[width,background-color] duration-200",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2",
                      activeSlide
                        ? "w-10 bg-slate-300/90 sm:w-12"
                        : "w-5 bg-slate-300/70 hover:bg-slate-400/80 sm:w-6",
                    )}
                  >
                    {activeSlide ? (
                      <span
                        key={progressKey}
                        aria-hidden="true"
                        className={cn(
                          "absolute inset-y-0 left-0 origin-left bg-brand-600 motion-reduce:w-full",
                          reducedMotion
                            ? "w-full"
                            : "w-full animate-carousel-progress",
                          (paused || manualPause) && !reducedMotion && "[animation-play-state:paused]",
                        )}
                        style={
                          !reducedMotion
                            ? { animationDuration: `${ROTATE_MS}ms`, transformOrigin: "left center" }
                            : undefined
                        }
                      />
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      <p className="sr-only" aria-live="polite">
        Slide {index + 1} of {count}
      </p>
    </div>
  );
}

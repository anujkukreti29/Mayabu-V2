import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Navy primary (not indigo/purple)
        brand: {
          50: "#f0f4f8",
          100: "#d9e2ec",
          200: "#bcccdc",
          300: "#9fb3c8",
          400: "#627d98",
          500: "#486581",
          600: "#334e68",
          700: "#243b53",
          800: "#102a43",
          900: "#0b1d33",
          950: "#071525",
        },
        accent: {
          DEFAULT: "#0f766e",
          soft: "#ccfbf1",
          strong: "#0d5c56",
        },
        page: "#f5f6f8",
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f0f2f5",
          elevated: "#ffffff",
        },
        ink: {
          DEFAULT: "#0b1220",
          soft: "#243447",
          muted: "#5c6b7a",
          faint: "#8b97a5",
        },
        line: {
          DEFAULT: "#e2e6eb",
          strong: "#c9d0d8",
        },
        header: "#0b1220",
        positive: "#047857",
        warning: "#b45309",
        danger: "#b91c1c",
        info: "#0369a1",
      },
      fontFamily: {
        sans: [
          "DM Sans",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
      },
      fontSize: {
        display: [
          "clamp(1.875rem, 1.2vw + 1.4rem, 2.5rem)",
          { lineHeight: "1.14", letterSpacing: "-0.028em", fontWeight: "700" },
        ],
        "title-lg": ["1.75rem", { lineHeight: "1.22", letterSpacing: "-0.02em", fontWeight: "600" }],
        "title-md": [
          "1.375rem",
          { lineHeight: "1.28", letterSpacing: "-0.015em", fontWeight: "600" },
        ],
        "title-sm": ["1.0625rem", { lineHeight: "1.35", fontWeight: "600" }],
        "body-lg": ["1.0625rem", { lineHeight: "1.6", fontWeight: "400" }],
        price: ["1.375rem", { lineHeight: "1.1", fontWeight: "700" }],
        label: ["0.75rem", { lineHeight: "1.3", letterSpacing: "0.04em", fontWeight: "600" }],
      },
      borderRadius: {
        xs: "0.375rem",
        sm: "0.5rem",
        md: "0.625rem",
        lg: "0.875rem",
        xl: "1rem",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px -16px rgba(15, 23, 42, 0.18)",
        lift: "0 2px 4px rgba(15, 23, 42, 0.05), 0 16px 36px -18px rgba(15, 23, 42, 0.28)",
        header: "0 8px 24px -18px rgba(0, 0, 0, 0.45)",
        focus: "0 0 0 3px rgba(15, 118, 110, 0.28)",
      },
      zIndex: {
        sticky: "10",
        dock: "40",
        nav: "50",
        dropdown: "60",
        overlay: "70",
        drawer: "80",
        skip: "100",
      },
      maxWidth: {
        content: "80rem",
        commerce: "90rem",
        reading: "46rem",
        prose: "42rem",
        narrow: "36rem",
      },
      spacing: {
        "section-y": "3.5rem",
        "nav-h": "4rem",
      },
      transitionDuration: {
        instant: "120ms",
        fast: "150ms",
        snappy: "180ms",
        standard: "220ms",
        smooth: "260ms",
        slow: "340ms",
        reveal: "420ms",
      },
      transitionTimingFunction: {
        mayabu: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      keyframes: {
        "carousel-progress": {
          "0%": { transform: "scaleX(0)" },
          "100%": { transform: "scaleX(1)" },
        },
        "reveal-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "press-in": {
          "0%": { transform: "translateY(0)" },
          "100%": { transform: "translateY(1px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "carousel-progress": "carousel-progress linear forwards",
        "reveal-up": "reveal-up 420ms cubic-bezier(0.22, 1, 0.36, 1) both",
        shimmer: "shimmer 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;

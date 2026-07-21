import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          500: "#4f46e5",
          600: "#4338ca",
          700: "#3730a3",
          950: "#1e1b4b",
        },
      },
      boxShadow: {
        soft: "0 12px 35px -18px rgba(15, 23, 42, 0.28)",
      },
      maxWidth: {
        content: "80rem",
      },
    },
  },
  plugins: [],
} satisfies Config;

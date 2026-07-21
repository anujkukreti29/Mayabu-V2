import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  test: {
    environment: "jsdom",
    setupFiles: ["./app/tests/setup.ts"],
    include: ["app/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**", "build/**", ".react-router/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["app/components/**/*.{ts,tsx}", "app/hooks/**/*.{ts,tsx}", "app/lib/**/*.{ts,tsx}"],
      exclude: [
        "app/**/*.test.{ts,tsx}",
        "app/routes/**",
        "app/root.tsx",
        "app/entry.*",
        "app/tests/**",
      ],
    },
  },
});

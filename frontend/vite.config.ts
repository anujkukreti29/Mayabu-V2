import { reactRouter } from "@react-router/dev/vite";
import { defineConfig, loadEnv } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), "");
  const apiTarget = (
    process.env.VITE_API_SERVER_URL ||
    process.env.VITE_API_BASE_URL ||
    fileEnv.VITE_API_SERVER_URL ||
    fileEnv.VITE_API_BASE_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");

  return {
    plugins: [reactRouter(), tsconfigPaths()],

    resolve: {
      dedupe: ["react", "react-dom", "react-router"],
    },

    optimizeDeps: {
      include: ["react", "react-dom", "react-dom/client", "react-router", "react-router/dom"],
    },

    build: {
      sourcemap: false,
      cssCodeSplit: true,
    },

    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: {
        // Browser same-origin /api/* → Mayabu FastAPI (SSR still uses VITE_API_SERVER_URL).
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
        },
      },
      warmup: {
        clientFiles: ["./app/entry.client.tsx", "./app/root.tsx", "./app/routes/**/*.tsx"],
      },
    },
  };
});

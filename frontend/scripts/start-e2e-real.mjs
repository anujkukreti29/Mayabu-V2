/**
 * Start frontend against the live local Mayabu API (port 8000).
 * Does not start mock-api. Requires API already running.
 */
import { spawn } from "node:child_process";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const apiBase = process.env.MAYABU_API_URL || "http://127.0.0.1:8000";

const frontend = spawn(npmCommand, ["run", "dev"], {
  stdio: "inherit",
  shell: process.platform === "win32",
  env: {
    ...process.env,
    VITE_API_BASE_URL: apiBase,
    VITE_API_SERVER_URL: apiBase,
    VITE_API_BROWSER_MODE: "same-origin",
    VITE_SITE_URL: "http://127.0.0.1:5173",
    VITE_APP_ENV: "test",
  },
});

function shutdown(signal = "SIGTERM") {
  if (!frontend.killed) frontend.kill(signal);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
frontend.on("exit", (code) => {
  process.exit(code ?? 0);
});

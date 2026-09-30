import { spawn } from "node:child_process";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const mock = spawn(process.execPath, ["scripts/mock-api-server.mjs"], {
  stdio: "inherit",
  env: { ...process.env, MOCK_API_PORT: "8001" },
  shell: false,
});
const frontend = spawn(npmCommand, ["run", "dev"], {
  stdio: "inherit",
  shell: process.platform === "win32",
  env: {
    ...process.env,
    VITE_API_BASE_URL: "http://127.0.0.1:8001",
    VITE_API_SERVER_URL: "http://127.0.0.1:8001",
    VITE_API_BROWSER_MODE: "same-origin",
    VITE_SITE_URL: "http://127.0.0.1:5173",
    VITE_APP_ENV: "test",
  },
});

function shutdown(signal = "SIGTERM") {
  if (!mock.killed) mock.kill(signal);
  if (!frontend.killed) frontend.kill(signal);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
mock.on("exit", (code) => {
  if (code && code !== 0) {
    shutdown();
    process.exit(code);
  }
});
frontend.on("exit", (code) => {
  shutdown();
  process.exit(code ?? 0);
});

import { access, readdir } from "node:fs/promises";
await access("build/server/index.js");
const assets = await readdir("build/server/assets");
if (!assets.some((name) => name.startsWith("server-build-") && name.endsWith(".js")))
  throw new Error("SSR server bundle is missing");
console.log("SSR server build verified.");

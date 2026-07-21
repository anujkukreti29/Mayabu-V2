import { access, readdir } from "node:fs/promises";
await access("build/client/index.html");
const assets = await readdir("build/client/assets");
if (!assets.some((name) => name.startsWith("entry.client-") && name.endsWith(".js")))
  throw new Error("Client entry bundle is missing");
if (!assets.some((name) => name.startsWith("manifest-") && name.endsWith(".js")))
  throw new Error("React Router client manifest is missing");
console.log("Client build verified.");

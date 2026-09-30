import { access } from "node:fs/promises";
const routes = [
  "index.html",
  "about/index.html",
  "platforms/index.html",
  "how-it-works/index.html",
  "contact/index.html",
  "privacy/index.html",
  "terms/index.html",
  "disclaimer/index.html",
];
for (const route of routes) await access(`build/client/${route}`);
console.log(`Verified ${routes.length} prerendered routes.`);

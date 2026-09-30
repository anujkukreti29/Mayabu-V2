import { absoluteUrl } from "~/lib/seo/metadata";
import { categorySitemapPaths } from "~/lib/seo/indexability";
import { urlsetXml, xmlResponse } from "~/lib/seo/sitemap";

export function loader() {
  const entries = categorySitemapPaths().map((path) => ({
    loc: absoluteUrl(path),
  }));
  return xmlResponse(urlsetXml(entries), 3600);
}

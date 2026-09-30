import { absoluteUrl } from "~/lib/seo/metadata";
import { supportedPlatformsText } from "~/lib/content/trust";

export function organizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Mayabu",
    url: absoluteUrl("/"),
    logo: absoluteUrl("/brand/mayabu-logo.png"),
    description:
      "Mayabu is an AI-assisted comparison engine that helps shoppers search once and compare product variants and retailer prices across stores in India.",
    areaServed: "IN",
  };
}

export function websiteJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Mayabu",
    url: absoluteUrl("/"),
    description: `Compare product prices and specifications across supported retailers in India. Currently comparing listings from ${supportedPlatformsText}.`,
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${absoluteUrl("/search")}?q={search_term_string}`,
      },
      "query-input": "required name=search_term_string",
    },
  };
}

export function jsonLdScript(data: Record<string, unknown>) {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

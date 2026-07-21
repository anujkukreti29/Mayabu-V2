import type { ProductDetail } from "~/lib/api/schemas";
import { absoluteUrl } from "~/lib/seo/metadata";
import { productSlug } from "~/lib/seo/slug";
import { validPrice } from "~/lib/formatting/price";

export function breadcrumbJsonLd(product: ProductDetail["product"]) {
  const categoryPath = product.category?.toLowerCase().includes("mobile")
    ? "/mobile-phones"
    : "/laptops";
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: absoluteUrl("/") },
      {
        "@type": "ListItem",
        position: 2,
        name: categoryPath === "/laptops" ? "Laptops" : "Mobile Phones",
        item: absoluteUrl(categoryPath),
      },
      {
        "@type": "ListItem",
        position: 3,
        name: product.title,
        item: absoluteUrl(`/products/${product.id}/${productSlug(product.title)}`),
      },
    ],
  };
}

export function productJsonLd(detail: ProductDetail) {
  const { product, offers } = detail;
  const prices = offers.map((offer) => offer.effective_price ?? offer.price).filter(validPrice);
  const data: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.title,
    url: absoluteUrl(`/products/${product.id}/${productSlug(product.title)}`),
  };
  if (product.image_url) data.image = [product.image_url];
  if (product.brand) data.brand = { "@type": "Brand", name: product.brand };
  const model = product.specs.model_codes?.[0];
  if (model) data.model = model;
  if (prices.length > 0) {
    data.offers = {
      "@type": "AggregateOffer",
      priceCurrency: "INR",
      lowPrice: Math.min(...prices),
      highPrice: Math.max(...prices),
      offerCount: prices.length,
    };
  }
  return data;
}

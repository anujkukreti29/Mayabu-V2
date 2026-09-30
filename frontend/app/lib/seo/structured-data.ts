import type { ProductDetail } from "~/lib/api/schemas";
import { absoluteUrl } from "~/lib/seo/metadata";
import { productSlug } from "~/lib/seo/slug";
import { validPrice } from "~/lib/formatting/price";
import { categoryBreadcrumbLabel, categorySearchHref } from "~/lib/product/detail-view";
import { normalizeProductImageUrl } from "~/lib/media/product-image-url";

export function breadcrumbJsonLd(product: ProductDetail["product"]) {
  const categoryPath = categorySearchHref(product.category);
  const categoryName = categoryBreadcrumbLabel(product.category);
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: absoluteUrl("/") },
      {
        "@type": "ListItem",
        position: 2,
        name: categoryName,
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
  const image = normalizeProductImageUrl(product.image_url);
  if (image) data.image = [image];
  if (product.brand) data.brand = { "@type": "Brand", name: product.brand };
  const model = product.model_codes?.[0] ?? product.specs?.model_codes?.[0];
  if (model) {
    data.model = String(model);
    data.mpn = String(model);
  }
  if (product.category) data.category = categoryBreadcrumbLabel(product.category);

  if (prices.length === 1) {
    data.offers = {
      "@type": "Offer",
      priceCurrency: "INR",
      price: String(prices[0]),
      url: data.url,
    };
  } else if (prices.length > 1) {
    data.offers = {
      "@type": "AggregateOffer",
      priceCurrency: "INR",
      lowPrice: String(Math.min(...prices)),
      highPrice: String(Math.max(...prices)),
      offerCount: prices.length,
    };
  }
  // No availability / aggregateRating / review — Mayabu does not claim stock or ratings.
  return data;
}

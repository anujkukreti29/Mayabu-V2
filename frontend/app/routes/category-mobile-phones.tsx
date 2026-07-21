import type { MetaFunction } from "react-router";
import { CategoryLanding } from "~/components/search/category-landing";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Compare Mobile Phone Prices and Variants in India | Mayabu",
    description:
      "Compare phone chipsets, RAM, storage, cameras, batteries, 5G support, price history, and offers across supported Indian ecommerce platforms.",
    path: "/mobile-phones",
  });

export default function MobilePhones() {
  return (
    <CategoryLanding
      eyebrow="Mobile research"
      title="Compare mobile phones by exact variant, features, and price"
      intro="Keep storage, RAM, colour, and model differences clear while comparing retailer offers and price history. Mobile coverage will expand as the backend indexes reliable products."
      intents={[
        "Phones under ₹20,000",
        "Phones under ₹30,000",
        "Camera phones",
        "Gaming phones",
        "Compact phones",
        "Premium phones",
      ]}
      checks={[
        "Chipset and model generation",
        "RAM, storage, and colour variant",
        "Display size, type, and refresh rate",
        "Battery capacity and charging support",
        "Camera hardware rather than marketing labels",
        "5G and regional model compatibility",
      ]}
    />
  );
}

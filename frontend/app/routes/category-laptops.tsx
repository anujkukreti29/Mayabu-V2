import type { MetaFunction } from "react-router";
import { CategoryLanding } from "~/components/search/category-landing";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Compare Laptop Prices and Variants in India | Mayabu",
    description:
      "Compare laptop models, processors, RAM, storage, graphics, displays, price history, and offers across supported Indian ecommerce platforms.",
    path: "/laptops",
  });

export default function Laptops() {
  return (
    <CategoryLanding
      eyebrow="Laptop research"
      title="Compare laptops by exact model, specifications, and price"
      intro="Find the correct laptop configuration before comparing offers across Amazon India, Flipkart, Croma, and Reliance Digital."
      intents={[
        "Laptops for coding",
        "Gaming laptops",
        "Thin and light laptops",
        "Business laptops",
        "Laptops under ₹50,000",
        "Laptops under ₹70,000",
        "Premium laptops",
      ]}
      checks={[
        "Processor family, exact CPU model, and generation",
        "RAM capacity and whether the listing describes the same configuration",
        "Storage capacity, type, and meaningful upgrade differences",
        "Dedicated or integrated graphics",
        "Screen size, resolution, and display type",
        "Model code and suffix differences that identify another variant",
      ]}
    />
  );
}

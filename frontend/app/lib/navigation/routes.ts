import { CATEGORY_ROUTE_BY_SLUG } from "~/lib/category/landing-registry";
import { PUBLIC_CATEGORY_SLUGS, categoryDisplayName } from "~/lib/search/categories";

export const routes = Object.freeze({
  home: "/",
  search: "/search",
  laptops: CATEGORY_ROUTE_BY_SLUG.laptop,
  smartphones: CATEGORY_ROUTE_BY_SLUG.smartphone,
  televisions: CATEGORY_ROUTE_BY_SLUG.television,
  refrigerators: CATEGORY_ROUTE_BY_SLUG.refrigerator,
  washingMachines: CATEGORY_ROUTE_BY_SLUG.washing_machine,
  tws: CATEGORY_ROUTE_BY_SLUG.tws,
  headphones: CATEGORY_ROUTE_BY_SLUG.headphones,
  cameras: CATEGORY_ROUTE_BY_SLUG.camera,
  /** @deprecated Use smartphones — kept for legacy imports. */
  mobilePhones: CATEGORY_ROUTE_BY_SLUG.smartphone,
  compare: "/compare",
  wishlist: "/wishlist",
  deals: "/deals",
  tracker: "/tracker",
  platforms: "/platforms",
  howItWorks: "/how-it-works",
  about: "/about",
  contact: "/contact",
  privacy: "/privacy",
  terms: "/terms",
  disclaimer: "/disclaimer",
  assistant: "/assistant",
  login: "/sign-in",
  signup: "/signup",
  checkEmail: "/check-email",
  account: "/account",
  admin: "/admin",
  verifyEmail: "/verify-email",
  forgotPassword: "/forgot-password",
  resetPassword: "/reset-password",
} as const);

export interface NavigationFeatures {
  deals: boolean;
  tracker: boolean;
}

export interface NavigationLink {
  to: string;
  label: string;
}

export const categoryLinks: readonly NavigationLink[] = PUBLIC_CATEGORY_SLUGS.map((slug) => ({
  to: CATEGORY_ROUTE_BY_SLUG[slug],
  label: categoryDisplayName(slug),
}));

export const futureCategories = [] as const;

/** Desktop primary nav — compact and truthful. */
export function primaryNavigation(_features?: NavigationFeatures): NavigationLink[] {
  void _features;
  return [
    { to: routes.compare, label: "Compare" },
    { to: routes.howItWorks, label: "How It Works" },
  ];
}

export function footerNavigation(features: NavigationFeatures) {
  return [
    {
      title: "Product",
      links: [
        { label: "Search Products", to: routes.search },
        ...categoryLinks.map(({ label, to }) => ({ label, to })),
        { label: "Compare Products", to: routes.compare },
        ...(features.deals ? [{ label: "Deals", to: routes.deals }] : []),
        ...(features.tracker ? [{ label: "Price Tracker", to: routes.tracker }] : []),
      ],
    },
    {
      title: "Trust & Support",
      links: [
        { label: "How Mayabu Works", to: routes.howItWorks },
        { label: "Supported Platforms", to: routes.platforms },
        { label: "Report a Data Issue", to: `${routes.contact}?topic=incorrect-data` },
        { label: "Contact Us", to: routes.contact },
      ],
    },
    {
      title: "Company",
      links: [
        { label: "About Mayabu", to: routes.about },
        { label: "Contact", to: routes.contact },
      ],
    },
    {
      title: "Legal",
      links: [
        { label: "Privacy Policy", to: routes.privacy },
        { label: "Terms of Use", to: routes.terms },
        { label: "Price Disclaimer", to: routes.disclaimer },
      ],
    },
  ] as const;
}

export const staticIndexablePaths = [
  routes.home,
  ...PUBLIC_CATEGORY_SLUGS.map((slug) => CATEGORY_ROUTE_BY_SLUG[slug]),
  routes.platforms,
  routes.howItWorks,
  routes.about,
  routes.contact,
  routes.privacy,
  routes.terms,
  routes.disclaimer,
] as const;

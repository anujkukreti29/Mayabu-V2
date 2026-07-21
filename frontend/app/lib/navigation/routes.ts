export const routes = Object.freeze({
  home: "/",
  search: "/search",
  laptops: "/laptops",
  mobilePhones: "/mobile-phones",
  compare: "/compare",
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
  login: "/login",
  signup: "/signup",
  account: "/account",
  admin: "/admin",
} as const);

export interface NavigationFeatures {
  deals: boolean;
  tracker: boolean;
}

export interface NavigationLink {
  to: string;
  label: string;
}

export const categoryLinks: readonly NavigationLink[] = [
  { to: routes.laptops, label: "Laptops" },
  { to: routes.mobilePhones, label: "Mobile Phones" },
];

export const futureCategories = ["Earbuds & Headphones", "Smartwatches", "Tablets"] as const;

export function primaryNavigation(features: NavigationFeatures): NavigationLink[] {
  return [
    { to: routes.compare, label: "Compare" },
    ...(features.deals ? [{ to: routes.deals, label: "Deals" }] : []),
    ...(features.tracker ? [{ to: routes.tracker, label: "Price Tracker" }] : []),
    { to: routes.platforms, label: "Supported Platforms" },
    { to: routes.howItWorks, label: "How It Works" },
    { to: routes.about, label: "About" },
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
  routes.laptops,
  routes.mobilePhones,
  routes.platforms,
  routes.howItWorks,
  routes.about,
  routes.contact,
  routes.privacy,
  routes.terms,
  routes.disclaimer,
] as const;

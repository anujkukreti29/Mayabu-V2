MAYABU v5.2
COMPLETE PRODUCTION FRONTEND MASTER PROMPT

React + Vite + TypeScript + React Router SSR/Prerendering + FastAPI

You are continuing the existing Mayabu project.

Mayabu is a production-grade AI buying assistant and price-intelligence
platform for Indian ecommerce.

The backend is already implemented as Mayabu v5.2 and must not be
redesigned, duplicated, bypassed, weakened, or replaced with
frontend-only logic.

Your task is to build a complete, secure, fast, accessible, responsive,
SEO-friendly, startup-grade frontend for Mayabu using React and Vite
while preserving all existing backend contracts and the current product
model.

Do not build a college-project dashboard.

Do not build a generic template with random gradients, oversized
illustrations, fake statistics, fabricated deals, fake AI answers,
placeholder reviews, or mock products presented as real data.

Build a serious consumer product that can be used by real users, scaled
gradually, indexed by search engines, and maintained by a professional
engineering team.

This is the controlling frontend specification.

When this specification conflicts with an older Mayabu frontend prompt,
this specification takes priority.

============================================================

1. # NON-NEGOTIABLE ARCHITECTURE

Use this architecture:

Browser
↓
React + Vite frontend
↓
React Router rendering layer for SSR, prerendering, and hydration
↓
FastAPI v5.2 REST API
↓
PostgreSQL + Redis
↓
Playwright scraper workers

Technology responsibilities:

- React is the frontend user-interface library.
- Vite is the frontend development and production build tool.
- React Router controls routes, loaders, navigation, route-level error
  boundaries, SSR, prerendering, and browser hydration.
- FastAPI remains the backend and system of record.
- PostgreSQL remains the primary database.
- Redis remains the caching, queue, request-coalescing, rate-limit, and
  distributed-coordination layer.
- Playwright is used by scraper workers and browser-based end-to-end
  tests.
- Playwright is not a database.

Do not use Next.js.

Do not use Nuxt, Angular, SvelteKit, or another frontend framework.

The frontend rendering process may run on Node.js only to:

- Render React HTML.
- Serve frontend assets.
- Handle React Router requests.
- Hydrate the application.
- Call FastAPI through typed API adapters.

The frontend rendering server must not become another business backend.

Do not move these responsibilities out of FastAPI:

- Product matching.
- Product-cluster decisions.
- Variant classification.
- Price calculations.
- Verification admission limits.
- Queue ownership.
- Scraper scheduling.
- Scraper retries.
- Circuit breakers.
- Authentication enforcement.
- Admin authorization.
- Database writes.
- Redis coordination.

FastAPI remains authoritative.

# ============================================================ 2. PRODUCT VISION

Mayabu helps users answer four questions:

1. Is this the correct product and variant?
2. Which platform currently offers the best known price?
3. Is the displayed price recent and trustworthy?
4. Should the user buy now, wait, verify the price, or compare another
   product?

Mayabu is not merely a price-comparison website.

Mayabu is a trusted buying-assistant and product-intelligence platform.

Mayabu must reduce these user problems:

- Accidentally comparing different RAM or storage variants.
- Confusing a related product with the exact product.
- Trusting an old price as if it were live.
- Opening several ecommerce tabs manually.
- Missing historical-low or unusually high-price context.
- Seeing a scraper failure represented as a zero price.
- Receiving vague AI advice without supporting evidence.
- Comparing listings that use different model numbers.
- Buying a product before confirming the final retailer price.

Initial production categories:

- Laptops.
- Mobile phones.

Future-ready electronics categories:

- Earbuds and headphones.
- Smartwatches.
- Tablets.
- Cameras.
- Monitors.
- Computer accessories.
- Other electronics.

Do not implement:

- Fashion.
- Grocery comparison.
- Food delivery.
- Quick commerce.
- Hotels.
- Flights.
- Cab comparison.

Keep category abstractions extensible so future verticals can be added
without rewriting the electronics frontend.

Supported platforms at launch:

- Amazon India.
- Flipkart.
- Croma.
- Reliance Digital.

# ============================================================ 3. EXISTING MAYABU v5.2 BACKEND

Treat Mayabu v5.2 as the source of truth.

The backend already provides or is designed around:

- PostgreSQL product clusters.
- Platform listings.
- Current best-known prices.
- Append-only price observations.
- Product search documents.
- Indexed product retrieval.
- Exact product matching.
- Similar-variant grouping.
- Related-product ranking.
- Price history.
- Durable background jobs.
- Redis caching.
- Queue leases.
- Retries.
- Dead jobs.
- Circuit breakers.
- Platform health monitoring.
- Direct product URL ingestion.
- Efficient live-price verification.
- Bounded verification workers.
- Product-scoped cache invalidation.
- Request coalescing.
- Per-client verification limits.
- Global verification limits.
- Admin metrics.
- Review workflows.

Do not make public search trigger discovery scraping.

Search pages and product pages must load stored backend data
immediately.

Live verification is an optional background action.

Live verification must never block the initial page render.

Do not change FastAPI behaviour merely to simplify the frontend unless a
real contract defect has been found and documented.

Do not duplicate backend matching logic in JavaScript.

Do not calculate exact-match confidence in the frontend.

Do not derive product identity from frontend title similarity.

Do not create frontend-only:

- Prices.
- MRP values.
- Discounts.
- Availability.
- Freshness timestamps.
- Matching classifications.
- AI confidence values.
- Seller ratings.

Backend timestamps, statuses, classifications, and product relationships
are authoritative.

# ============================================================ 4. REQUIRED FRONTEND STACK

Use:

- React 19 or the approved stable React version in the repository.
- Vite.
- TypeScript with strict mode.
- React Router using Framework Mode or its approved SSR-capable Data
  Router configuration.
- Vite SSR.
- React DOM server rendering.
- Client hydration.
- Tailwind CSS.
- Radix UI primitives where useful.
- shadcn/ui-style components where useful.
- TanStack Query.
- Zod.
- React Hook Form.
- Recharts or an equally lightweight accessible chart library.
- Lucide React icons.
- React error boundaries.
- Route-level error boundaries.
- Vitest.
- React Testing Library.
- Mock Service Worker where useful.
- Playwright for frontend end-to-end tests.
- ESLint.
- Prettier.
- npm unless the repository already uses another package manager
  consistently.

Preferred routing implementation:

- React Router Framework Mode.
- Vite integration.
- SSR enabled.
- Route loaders for initial data.
- Client-side navigation after hydration.
- Production serving through the approved React Router server adapter or
  another documented Node runtime.

Do not add a dependency only because it is popular.

Do not install multiple libraries that solve the same problem.

Do not introduce Redux, Zustand, MobX, or another global-state library
unless a real cross-application state requirement cannot be handled by:

- URL state.
- Route state.
- TanStack Query.
- React context.
- Local component state.

Use React document metadata components or another SSR-compatible
metadata implementation.

SEO-critical metadata must appear in the initial HTML.

Do not rely only on useEffect for:

- Title tags.
- Canonical links.
- Meta descriptions.
- Robots directives.
- Structured data.

# ============================================================ 5. SEO RENDERING ARCHITECTURE

A client-only empty application shell is not sufficient for Mayabu's
indexable public pages.

Implement React + Vite with SSR and prerendering.

Preferred implementation:

- React Router Framework Mode.
- Vite build integration.
- Server rendering enabled.
- Route loaders call FastAPI through the typed API layer.
- Initial route data is rendered into HTML.
- Browser hydration activates the application.
- Later navigation uses client-side routing.

Acceptable lower-level implementation:

- Vite SSR.
- entry-client.tsx.
- entry-server.tsx.
- ReactDOMServer.
- React Router createStaticHandler.
- React Router createStaticRouter.
- React Router StaticRouterProvider.
- A minimal Node frontend rendering server.

The Node frontend server may:

- Render React.
- Serve built assets.
- handle canonical redirects.
- return correct route status codes.
- proxy or call public FastAPI endpoints through typed adapters.

The Node frontend server must not:

- Replace FastAPI.
- Query PostgreSQL directly.
- Query Redis directly.
- Run Playwright scrapers.
- Own verification jobs.
- calculate matching.
- store business data.

Prerender these stable routes when possible:

- /
- /about
- /platforms
- /how-it-works
- /contact
- /privacy
- /terms
- /disclaimer
- /laptops
- /mobile-phones

Server-render these routes from FastAPI data:

- Canonical product pages.
- Stable category pages.
- Stable backend-supported deal pages.

Use noindex or client-only rendering for:

- Internal account pages.
- Admin pages.
- Verification job pages.
- Arbitrary search-query pages.
- Infinite filter combinations.
- Sort combinations.
- Temporary compare URLs.
- Empty product pages.
- Removed product pages.
- Error pages.

Do not serve materially different content to search engines and users.

Do not implement crawler-only hidden rendering.

Users and search engines must receive equivalent meaningful content.

# ============================================================ 6. ENVIRONMENT VARIABLES

Create one validated configuration module.

Required:

VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_SITE_URL=http://localhost:5173
VITE_APP_ENV=development

Optional feature flags:

VITE_ENABLE_AUTH=false
VITE_ENABLE_TRACKER=false
VITE_ENABLE_ASSISTANT=false
VITE_ENABLE_ADMIN=false
VITE_ENABLE_DEALS=false
VITE_ENABLE_ANALYTICS=false
VITE_ENABLE_COOKIE_BANNER=false

Optional rendering configuration:

VITE_RENDER_MODE=ssr
VITE_CANONICAL_HOST=http://localhost:5173

Rules:

- Never scatter backend URLs throughout components.
- Never expose PostgreSQL credentials.
- Never expose Redis credentials.
- Never expose proxy credentials.
- Never expose Playwright credentials.
- Never expose scraper secrets.
- Never expose admin tokens.
- Validate required configuration during startup and build.
- Production builds must fail clearly when required configuration is
  missing.
- Only intentionally public VITE\_ variables may enter browser bundles.
- Never place confidential values in VITE\_ variables.
- Support development, staging, and production API origins.

# ============================================================ 7. FRONTEND ARCHITECTURE PRINCIPLES

Follow:

- Feature-based modular structure.
- Reusable presentational components.
- Typed API adapters.
- Runtime validation at API boundaries.
- Route-level code splitting.
- SSR-compatible public components.
- Progressive enhancement.
- No duplicated business rules.
- No direct fetch calls inside visual components.
- No fake production data.
- No silent failures.
- No unsafe scraped HTML.
- No unnecessary global state.
- No oversized god components.
- No frontend product-matching implementation.
- No frontend-generated freshness claims.
- No price without currency and context.
- No unsupported route presented as working.
- No dead navigation links.
- No Lorem Ipsum.
- No fake testimonials.
- No fake review counts.
- No fake active-user counts.
- No fake savings statistics.
- No fake AI confidence percentages.
- No unsupported marketing claims.

Keep business data separate from presentation.

Keep route loading separate from UI primitives.

Keep formatting utilities deterministic and tested.

Keep query keys centralised.

Keep analytics vendor-neutral.

Keep feature flags centralised.

Keep reusable user-visible copy in a typed copy/constants layer.

# ============================================================ 8. RECOMMENDED FOLDER STRUCTURE

frontend/
app/
root.tsx
routes.ts
entry.client.tsx
entry.server.tsx
routes/
home.tsx
search.tsx
category-laptops.tsx
category-mobile-phones.tsx
product-detail.tsx
compare.tsx
deals.tsx
tracker.tsx
platforms.tsx
how-it-works.tsx
about.tsx
contact.tsx
privacy.tsx
terms.tsx
disclaimer.tsx
assistant.tsx
login.tsx
signup.tsx
account.tsx
account-saved.tsx
account-alerts.tsx
account-history.tsx
account-settings.tsx
admin.tsx
admin-scrapers.tsx
admin-matching.tsx
admin-anomalies.tsx
admin-verifications.tsx
admin-jobs.tsx
admin-reports.tsx

src/
components/
ui/
layout/
navigation/
search/
product/
pricing/
verification/
comparison/
charts/
trust/
forms/
feedback/
account/
admin/
seo/

    features/
      search/
      products/
      categories/
      price-history/
      verification/
      comparison/
      deals/
      tracker/
      assistant/
      admin/

    lib/
      api/
        client.ts
        schemas.ts
        errors.ts
        search.ts
        products.ts
        verification.ts
        price-history.ts
        tracker.ts
        admin.ts

      query/
        client.ts
        keys.ts
        hydration.ts

      seo/
        metadata.ts
        canonical.ts
        structured-data.ts
        robots.ts
        sitemap.ts

      analytics/
      auth/
      config/
      formatting/
      security/
      storage/
      validation/

    hooks/
    types/
    constants/
    copy/
    styles/
    tests/

public/
icons/
logos/
social/

scripts/
prerender.ts
generate-sitemap.ts
verify-seo.ts

e2e/
index.html
vite.config.ts
tsconfig.json
package.json
.env.example
README.md

Keep feature logic close to its feature.

Place components in components/ui only when they are genuinely reusable.

Do not create one giant components directory.

Do not create one generic utils.ts containing unrelated logic.

# ============================================================ 9. ROUTES AND INDEXING POLICY

Public routes:

- /
- /search
- /laptops
- /mobile-phones
- /products/:productId/:productSlug?
- /compare
- /deals
- /tracker
- /platforms
- /how-it-works
- /about
- /contact
- /privacy
- /terms
- /disclaimer

Feature-flag until backend support exists:

- /assistant
- /login
- /signup
- /account
- /account/saved
- /account/alerts
- /account/history
- /account/settings

Admin routes:

- /admin
- /admin/scrapers
- /admin/matching
- /admin/anomalies
- /admin/verifications
- /admin/jobs
- /admin/reports

Indexing policy:

Home:

- index, follow.

About:

- index, follow.

How It Works:

- index, follow.

Platforms:

- index, follow.

Category pages with unique content:

- index, follow.

Valid product pages:

- index, follow.

Empty product pages:

- noindex.
- Return a real 404.

Permanently removed products:

- Return 404 or 410 as appropriate.

Arbitrary search-query pages:

- noindex, follow by default.

Filter and sort combinations:

- noindex, follow or canonicalise according to the route policy.

Compare:

- noindex, follow.

Account:

- noindex.

Admin:

- noindex, nofollow.

Verification jobs:

- Never index.

Canonical product route:

/products/{productId}/{normalised-product-slug}

The product ID remains the stable identifier.

The slug is for readability and SEO.

If an outdated slug is requested, redirect permanently to the current
canonical slug.

Do not use the title alone as the identifier.

# ============================================================ 10. DESIGN SYSTEM

Visual direction:

- Clean consumer-technology design.
- Light-first theme.
- White and subtle neutral surfaces.
- Indigo or blue primary accent.
- Green only for positive deal or verification states.
- Amber for stale, waiting, and caution states.
- Red for errors, blocked checks, destructive actions, and high-price
  warnings.
- Soft borders.
- Restrained shadows.
- Medium-radius cards.
- Strong information hierarchy.
- High readability.
- Generous whitespace.
- Neutral product-image backgrounds.
- Minimal decorative motion.
- No excessive gradients.
- No glassmorphism overload.
- No giant decorative illustrations.
- No cluttered public dashboards.
- No random neon aesthetic.

Typography:

- One modern sans-serif family.
- Prefer a variable font when performance remains acceptable.
- Clear display, heading, body, label, metadata, and caption scales.
- Clamp product titles safely.
- Use tabular numerals for prices where supported.
- Do not use extremely light text for essential information.

Spacing:

- Consistent spacing tokens.
- Mobile-first scale.
- Clear grouping.
- Primary actions must be obvious.
- Prefer whitespace over dense card walls.

Create tokens for:

- Backgrounds.
- Surfaces.
- Text.
- Borders.
- Primary accent.
- Secondary accent.
- Success.
- Warning.
- Danger.
- Information.
- Spacing.
- Radius.
- Shadows.
- Typography.
- Breakpoints.
- Motion.
- Easing.
- Z-index.
- Container widths.

Minimum touch target:

44 by 44 CSS pixels.

# ============================================================ 11. GLOBAL BRAND COPY

Brand:

Mayabu

Tagline:

Compare smarter. Buy better.

Primary value statement:

Compare exact product variants, platform prices, price history, and
verification freshness before you buy.

Core trust statement:

Mayabu shows the best known price and when it was last checked. Seller
prices, stock, coupons, delivery eligibility, and checkout totals can
still change.

Required price disclaimer:

Prices, stock, delivery eligibility, coupons, and availability may
change on seller websites. Always verify the final amount before
purchase.

Required seller relationship statement:

Mayabu is a product-discovery and price-intelligence service. Mayabu is
not the seller of the products shown.

Do not use:

- Guaranteed lowest price.
- Guaranteed live price.
- Always accurate.
- 100% current.
- Best price guaranteed.
- Mayabu-certified seller unless a real programme exists.
- AI knows the perfect product for you.

# ============================================================ 12. NAVBAR

Create a sticky professional navbar.

Desktop order:

1. Mayabu logo linked to /.
2. Main search field or search trigger.
3. Categories dropdown.
4. Deals when enabled.
5. Compare.
6. Price Tracker when enabled.
7. Supported Platforms.
8. How It Works.
9. About.
10. Log in and Create account when enabled.
11. Profile menu when authenticated.

Exact labels:

- Categories
- Deals
- Compare
- Price Tracker
- Supported Platforms
- How It Works
- About
- Log in
- Create account
- My account
- Saved products
- Price alerts
- Search history
- Settings
- Log out

Categories dropdown:

- Laptops
- Mobile Phones
- Earbuds & Headphones — Coming later
- Smartwatches — Coming later
- Tablets — Coming later

Do not make coming-later items appear interactive unless they have a real
destination.

Desktop behaviour:

- Keep the navbar compact.
- Keep search accessible during scroll.
- Do not overcrowd top-level navigation.
- Use a More menu if required.
- Highlight the active route.
- Do not rely only on colour.
- Support keyboard navigation.

Mobile behaviour:

- Menu button label: Open menu.
- Open-state label: Close menu.
- Use an accessible drawer.
- Prevent background scrolling.
- Move focus into the drawer.
- Restore focus after closing.
- Provide a sticky search shortcut.

Optional mobile bottom navigation:

- Home
- Search
- Compare
- Tracker when enabled
- Profile when enabled

Navbar search placeholder:

Search products, model numbers, or specifications

Navbar search accessible button label:

Search Mayabu

# ============================================================ 13. FOOTER

Brand block:

Mayabu

Tagline:

Compare smarter. Buy better.

Supporting copy:

Search electronics, confirm the exact variant, compare platform offers,
review price history, and verify a recent price before you buy.

Product column:

- Search Products
- Laptops
- Mobile Phones
- Deals when enabled
- Compare Products
- Price Tracker when enabled

Trust & Support column:

- How Mayabu Works
- Supported Platforms
- Report a Data Issue
- Contact Us

Company column:

- About Mayabu
- Contact

Do not show Careers, Press, or Partners until real pages exist.

Legal column:

- Privacy Policy
- Terms of Use
- Price Disclaimer
- Cookie Preferences only when consent controls exist

Supported-platform text:

Currently supported: Amazon India, Flipkart, Croma, and Reliance Digital.

Footer disclaimer:

Prices, stock, delivery eligibility, coupons, and availability may
change on seller websites. Always verify the final amount before
purchase.

Trademark statement:

Mayabu is not affiliated with or endorsed by the listed marketplaces
unless explicitly stated. Marketplace names and trademarks belong to
their respective owners.

Copyright:

© {current year} Mayabu. All rights reserved.

# ============================================================ 14. HOME PAGE

Route:

/

Indexing:

index, follow

SEO title:

Mayabu: Compare Electronics Prices in India

SEO description:

Compare exact laptop and mobile variants, prices across Amazon,
Flipkart, Croma, and Reliance Digital, price history, and verification
freshness with Mayabu.

Open Graph title:

Compare smarter. Buy better with Mayabu.

Open Graph description:

Find the correct electronics variant, compare platform offers, review
price history, and request a recent price verification before buying.

H1:

Find the best place to buy electronics in India

Supporting paragraph:

Compare exact product variants, prices across trusted platforms, price
history, and verification freshness before you buy.

Primary search placeholder:

Search a laptop, phone, model number, or specification

Primary button:

Search products

Helper text:

Try a model name, SKU, processor, RAM, storage, or a natural-language
query.

Suggested queries:

- Gaming laptop under ₹70,000
- MacBook Air best price
- ASUS Vivobook 14 Ultra 5
- Best phone under ₹30,000

Hero trust line:

Prices from Amazon India, Flipkart, Croma, and Reliance Digital.

Do not add fake user counts.

Do not add fake savings claims.

Platform strip heading:

Compare offers from supported Indian retailers

Platform labels:

- Amazon India
- Flipkart
- Croma
- Reliance Digital

Supporting copy:

Mayabu groups matching listings, keeps material variants separate, and
shows when each offer was last checked.

Popular categories eyebrow:

Shop by category

Heading:

Start with the electronics you are researching

Laptop card:

Title:
Laptops

Description:
Compare processors, RAM, storage, graphics, displays, model codes, and
platform prices.

CTA:
Explore laptops

Mobile card:

Title:
Mobile Phones

Description:
Compare chipsets, RAM, storage, cameras, batteries, connectivity,
variants, and offers.

CTA:
Explore mobile phones

Price-drop section eyebrow:

Recent movement

Heading:

Price drops worth checking

Supporting text:

Products whose recorded price has fallen based on Mayabu's stored
observations.

Use backend data only.

Hide the section if no supported endpoint or trustworthy data exists.

Do not show fabricated deals.

How Mayabu Works eyebrow:

Simple product research

Heading:

From search to a more confident purchase

Step 1:

Search the product

Use a product name, model number, or the specifications you need.

Step 2:

Confirm the exact variant

Mayabu separates exact matches, similar variants, and related
alternatives.

Step 3:

Compare platform offers

Review the best known price, availability, and freshness across
supported retailers.

Step 4:

Check price history

Understand how the recorded price has moved over time.

Step 5:

Verify before buying

Request a recent background check for a known store listing without
blocking the page.

CTA:

See how verification works

Trust section heading:

Freshness you can understand

Primary copy:

Mayabu never presents an old stored price as a guaranteed live price.
Every offer includes its latest available freshness context.

Trust item:

Exact matches stay separate

Material differences such as RAM, storage, generation, model suffix, and
screen size are not hidden.

Trust item:

Cached prices load immediately

Product pages do not wait for a scraper before showing useful stored
data.

Trust item:

Verification is optional

A verification request checks known product-detail listings in the
background and may be queued or rate-limited.

Trust item:

Seller checkout remains final

Coupons, stock, delivery eligibility, and final checkout totals can
change on the seller website.

Visible FAQ questions:

Does Mayabu sell products?

Answer:

No. Mayabu helps users compare product information and external retailer
offers. Purchases are completed on the seller's website.

Are Mayabu prices live?

Answer:

Mayabu shows the best known stored price and when it was last checked.
Users can request a recent verification for supported listings, but
seller prices can still change.

How does Mayabu avoid mixing different variants?

Answer:

Mayabu uses backend product identity, model, and specification matching.
Exact products, similar variants, and related products are presented
separately.

Which stores does Mayabu support?

Answer:

Mayabu currently supports Amazon India, Flipkart, Croma, and Reliance
Digital.

Why should I verify a price before buying?

Answer:

Stock, coupons, delivery location, payment offers, and checkout prices
may change after Mayabu last recorded an offer.

Do not add FAQ structured data automatically.

# ============================================================ 15. CATEGORY LANDING PAGES

Routes:

- /laptops
- /mobile-phones

These pages must contain unique editorial content.

They must not be only filtered search-result pages.

Laptops SEO title:

Compare Laptop Prices and Variants in India | Mayabu

Laptops description:

Compare laptop models, processors, RAM, storage, graphics, displays,
price history, and offers across supported Indian ecommerce platforms.

Laptops H1:

Compare laptops by exact model, specifications, and price

Supporting copy:

Find the correct laptop configuration before comparing offers across
Amazon India, Flipkart, Croma, and Reliance Digital.

Suggested laptop intents:

- Laptops for coding
- Gaming laptops
- Thin and light laptops
- Business laptops
- Laptops under ₹50,000
- Laptops under ₹70,000
- Premium laptops

Mobile SEO title:

Compare Mobile Phone Prices and Variants in India | Mayabu

Mobile description:

Compare phone chipsets, RAM, storage, cameras, batteries, 5G support,
price history, and offers across supported Indian ecommerce platforms.

Mobile H1:

Compare mobile phones by exact variant, features, and price

Supporting copy:

Keep storage, RAM, colour, and model differences clear while comparing
retailer offers and price history.

Suggested mobile intents:

- Phones under ₹20,000
- Phones under ₹30,000
- Camera phones
- Gaming phones
- Compact phones
- Premium phones

Only create indexable intent pages when useful data and unique content
exist.

# ============================================================ 16. SEARCH RESULTS PAGE

Route:

/search?q={query}

Default indexing:

noindex, follow

Title pattern:

Search Results for “{query}” | Mayabu

Sanitise and length-limit query text before using it in metadata.

H1:

Search results for “{query}”

Count copy:

{count} products found

Use singular grammar for one product.

Render sections in this order:

1. Exact matches.
2. Similar variants.
3. Related products.

Never combine them into an unexplained list.

Exact section:

Heading:
Exact matches

Description:
The same product identity and configuration based on Mayabu's matching
data.

Similar variants section:

Heading:
Similar variants

Description:
Related configurations with important differences such as RAM, storage,
colour, generation, or model suffix.

Difference label:
Variant difference

Examples:

- 16GB RAM instead of 8GB
- 1TB storage instead of 512GB
- Different processor generation
- Different model suffix
- Different colour

Only show backend-supported differences.

Related section:

Heading:
Related products

Description:
Alternative products that may fit a similar requirement but are not the
same model or variant.

Search control labels:

- Filters
- Sort by
- Clear all
- Apply filters
- Reset filters
- Show results

Sort options:

- Best match
- Lowest price
- Highest price
- Recently checked
- Largest discount only when valid

Do not show popularity sorting without a popularity signal.

Common filters:

- Category
- Brand
- Price range
- Platform
- Availability
- Discount
- Freshness

Laptop filters:

- Processor brand
- Processor family
- Processor model
- RAM
- Storage
- GPU
- Screen size
- Display type
- Operating system
- Weight when available

Mobile filters:

- Chipset
- RAM
- Storage
- Battery
- Main camera
- 5G
- Display size
- Display type
- Refresh rate when available

Generate filters from backend capabilities or category configuration.

Do not deeply hardcode every filter in one page.

Pagination rules:

- Use backend cursor pagination when available.
- Preserve query, filters, sort, and cursor in the URL.
- Support browser back and forward.
- Avoid unbounded infinite scrolling.
- Use explicit pagination or Load More.
- Do not index every filter combination.

Pagination labels:

- Load more products
- Previous page
- Next page

Search states:

Initial heading:

Search for an electronics product

Initial text:

Enter a model name, model number, brand, processor, RAM, storage, or the
type of product you need.

Loading label:

Searching Mayabu…

Empty heading:

No matching product found

Empty text:

Try a shorter model name, remove one specification, or search for the
product family instead.

Unsupported heading:

Mayabu does not support this category yet

Unsupported text:

Mayabu currently focuses on laptops and mobile phones. More electronics
categories will be added gradually.

Backend unavailable heading:

Search is temporarily unavailable

Backend unavailable text:

Mayabu could not reach the product service. Please try again in a
moment.

Invalid query heading:

Enter a more specific product search

Invalid query text:

Use a product name, model number, brand, or useful specification.

Partial notice:

Some product data could not be loaded. Available results are shown
below.

End text:

You have reached the end of these results.

Cancel obsolete requests when the query changes.

Debounce suggestions.

Submit explicit searches immediately.

# ============================================================ 17. PRODUCT CARDS

Required content:

- Product image.
- Canonical product title.
- Brand.
- Category.
- Key specifications.
- Best known price.
- Valid MRP.
- Valid discount.
- Best platform.
- Platform count.
- Availability.
- Price-check timestamp.
- Backend-provided deal badge.
- Relationship label.

Relationship labels:

- Exact match
- Similar variant
- Related product

Freshness labels:

- Verified recently
- Verified {relative time}
- Last checked {relative time}
- Last known price
- Verification unavailable

Primary action:

View product details

Secondary actions:

- Compare prices
- Add to compare
- Remove from compare
- Track price when enabled

Do not place more than two prominent actions on a normal card.

Image fallback:

Product image unavailable

Price rules:

- Never display ₹0.
- Never display NaN.
- Never display undefined.
- Never calculate discount with invalid MRP.
- Never invent an MRP.
- Clearly label unavailable offers.
- Keep the last valid price after verification failure.

Platform count:

Available on 1 platform

Available on {count} platforms

Missing price:

Price unavailable

Out of stock:

Out of stock

Limited data:

Limited price data

# ============================================================ 18. PRODUCT DETAIL PAGE

Canonical route:

/products/:productId/:productSlug

Indexing:

index, follow only when the product exists and contains useful content.

SEO title:

{Product Name}: Price Comparison and History | Mayabu

SEO description:

Compare the {Product Name} across supported Indian retailers, review
specifications, the best known price, price history, availability, and
verification freshness.

Open Graph title:

{Product Name} price comparison | Mayabu

Open Graph description:

Compare platform offers, price history, and the latest available
verification status for {Product Name}.

H1:

Canonical backend product title.

Breadcrumbs:

- Home
- Laptops or Mobile Phones
- Product name

Add BreadcrumbList structured data.

Product identity section:

- Image gallery.
- Canonical title.
- Brand.
- Model code.
- Category.
- Key specifications.
- Variant summary.
- Report wrong match action.

Labels:

- Product details
- Model
- Variant
- Key specifications
- Report wrong product match

Helper text:

Tell Mayabu when listings from different products or variants have been
grouped incorrectly.

Best offer heading:

Best known offer

Labels:

- Best known price
- Available from
- Last verified
- Availability
- View on store
- Verify best price

Never use:

- Live price
- Guaranteed current price

Allowed copy:

- Verified 3 minutes ago
- Last checked 2 hours ago
- Checking the store now
- Verification queued
- Could not verify right now
- Last known price

Nearby disclaimer:

The final price, stock, delivery, coupon, and payment offer are confirmed
on the seller website.

Platform section heading:

Compare platform offers

Supporting text:

Review current or last known prices and when each listing was last
checked.

Desktop columns:

- Platform
- Price
- MRP
- Discount
- Availability
- Last verified
- Status
- Action

Mobile:

Use stacked cards.

Offer button:

View on {platform}

Unavailable link:

Store link unavailable

No offers heading:

No matched offers available

No offers text:

Mayabu has identified this product, but no active matched retailer
listing is available yet.

Price-history heading:

Price history

Supporting text:

Recorded prices help you understand recent movement. Historical data
does not guarantee a future price.

Show:

- Price chart.
- Current best.
- Lowest observed.
- Highest observed.
- Average observed.
- Date range.
- Platform filter when useful.
- Limited-data state.
- Missing-data state.

Range labels:

- 30 days
- 90 days
- 6 months
- 1 year
- All available data

Limited-data heading:

More price history is needed

Limited-data text:

Mayabu does not yet have enough observations to show a reliable trend
for this product.

Missing-data heading:

Price history unavailable

Missing-data text:

No historical observations are available for this product yet.

Do not fabricate a trend.

Do not imply prediction from historical data.

Insight heading:

Mayabu buying insight

Allowed example:

This price is close to the lowest price observed by Mayabu. The offer
was verified recently, but the final seller price and stock can still
change.

Disclosure:

Why Mayabu says this

Possible evidence:

- Current price relative to history.
- Verification recency.
- Number of offers.
- Availability.
- Data limitations.

Possible badges:

- Good recorded price
- Near observed low
- Price is above recent average
- Consider waiting
- Limited data
- Verify before buying

Do not invent confidence.

Do not claim future-price certainty.

Relationship sections:

- Same product across platforms
- Similar variants
- Related products

Similar variants description:

These products are closely related but may differ in RAM, storage,
processor generation, colour, model suffix, screen, or another important
specification.

Related products description:

These alternatives may satisfy a similar need but are not the same
product.

# ============================================================ 19. LIVE PRICE VERIFICATION

Public endpoints:

POST /api/products/{product_id}/verify-price
GET /api/verification-jobs/{task_id}
GET /api/products/{product_id}/verification-status

Frontend guarantees:

- Cached PostgreSQL prices display immediately.
- The page never waits for scraping.
- Best-offer verification is the default.
- All-offer verification checks no more than four listings.
- Multiple users can share one existing task.
- Requests can be fresh, joined, queued, delayed, limited, blocked, or
  failed.
- Failure never removes the last valid price.

Primary action:

Verify best price

Secondary action:

Verify all offers

Only show Verify all offers when multiple known listings exist.

Best-price tooltip:

Checks the currently best known retailer listing in the background.

All-offer tooltip:

Checks up to four known retailer listings. This may take longer.

State: fresh

Heading:
Price verified recently

Message:
Mayabu already has a recent verification for this listing, so a new
scraper job was not needed.

State: stale

Heading:
A newer check may be useful

Message:
This is the last known price. You can request a recent verification
before visiting the store.

State: eligible

Heading:
Ready to verify

Message:
Mayabu can check the selected known store listing in the background.

State: requesting

Heading:
Preparing verification

Message:
Mayabu is checking whether a recent verification or active shared job
already exists.

State: queued

Heading:
Verification queued

Message:
Your request is waiting for an available verification worker. The last
known price remains visible.

State: joined

Heading:
Joined an existing verification

Message:
Another user already requested this listing, so Mayabu is sharing the
same verification job instead of creating another scraper request.

State: running

Heading:
Checking the store now

Message:
Mayabu is verifying the selected listing. You can continue using the
page while the check runs.

State: completed unchanged

Heading:
Price verified

Message:
The latest observed price matches the previously stored price.

State: completed changed

Heading:
Price changed

Message:
The observed price changed from {oldPrice} to {newPrice}.

State: out of stock

Heading:
Currently out of stock

Message:
The store listing was checked and appears to be out of stock. The
previous valid price remains available as historical context.

State: temporarily unavailable

Heading:
Store temporarily unavailable

Message:
Mayabu could not access this store listing right now. The last known
price remains visible.

State: blocked or captcha

Heading:
Verification blocked by the store

Message:
The retailer blocked the automated check or requested a captcha. Open
the seller page to confirm the current price.

State: rate limited

Heading:
Too many verification requests

Message:
Mayabu is limiting verification traffic to protect service reliability.
Please use the recent result or try again later.

State: queue full

Heading:
Verification queue is busy

Message:
Mayabu cannot accept another verification job right now. The last known
price remains available.

State: cooldown

Heading:
Recently checked

Message:
This listing is in a short cooldown period. Use the latest verification
result or try again later.

State: failed

Heading:
Could not verify right now

Message:
The verification did not complete successfully. Mayabu has kept the
last valid known price.

State: expired

Heading:
Verification status expired

Message:
The browser stopped waiting, but the backend job may still continue.
Refresh the product status later.

State: no offers

Heading:
No listing available to verify

Message:
Mayabu does not currently have a known retailer listing for this
product.

Verification behaviour:

- Keep the cached offer visible.
- Do not replace the price with a spinner.
- Show non-blocking progress.
- Poll with controlled backoff.
- Pause polling when the page remains hidden.
- Resume safely.
- Never poll unnecessarily fast.
- Never create duplicate mutations on rerender.
- Persist active task IDs where useful.
- Allow opening the store immediately.

Suggested polling:

- Every 2 seconds for the first 10 seconds.
- Every 4 seconds afterward.
- Stop browser polling after a reasonable timeout.
- Allow the backend task to continue.

After completion:

- Update product query data.
- Update offer query data.
- Update verification status.
- Update price history only when relevant.
- Announce results through an ARIA live region.
- Highlight changes without disruptive animation.

When delayed:

- Keep last known price visible.
- Explain load control.
- Keep View on store available.

Use:

- Verified {relative time}
- Last known price
- Checking the store now
- Verification queued
- Price changed from {oldPrice} to {newPrice}
- Could not verify right now

Never use:

- Guaranteed live price
- 100 percent current
- Always accurate
- Instant live scraping

# ============================================================ 20. COMPARE PAGE

Route:

/compare?products={id1},{id2}

Indexing:

noindex, follow

SEO title:

Compare Products | Mayabu

H1:

Compare products side by side

Supporting text:

Review specifications, best known prices, platform availability, price
history, and freshness before choosing.

Allow two to four products.

Include:

- Product search.
- Add product.
- Shareable comparison URL.
- Side-by-side images.
- Titles.
- Model codes.
- Specification differences.
- Best known prices.
- Freshness timestamps.
- Platform counts.
- Price-history summary.
- Strengths and tradeoffs.
- Remove action.
- Clear action.

Labels:

- Add a product
- Remove
- Clear comparison
- Copy comparison link
- Comparison link copied

Possible evidence-based winner labels:

- Best current value
- Lower price
- Better performance
- Better portability
- More storage
- Longer recorded price history

Do not invent a total score.

Do not compare missing values as zero.

Mobile:

- Use tabs or controlled horizontal scrolling.
- Keep product names visible.
- Do not create an unusable table.

Empty heading:

Choose products to compare

Empty text:

Add two to four products from search results or product pages.

# ============================================================ 21. DEALS PAGE

Show only when the backend provides trustworthy deal data.

Route:

/deals

SEO title:

Electronics Price Drops and Deals in India | Mayabu

SEO description:

Explore recorded electronics price drops, near-historical-low offers,
and recently verified prices across supported Indian retailers.

H1:

Electronics price drops worth checking

Supporting text:

Deals are based on Mayabu's recorded price observations and
verification freshness. Final seller prices and stock can change.

Sections:

- Largest verified price drops
- Near historical low
- Recently verified offers
- Good recorded value

Filters:

- Category
- Platform
- Price range
- Freshness

Every deal card must show:

- Timestamp.
- Price-change basis.
- Platform.
- Product relationship.
- Disclaimer.

Do not call something a deal only because an MRP discount exists.

Do not fabricate deal percentages.

Hide unsupported sections.

Unavailable heading:

Verified deals are coming soon

Unavailable text:

Mayabu will show this page after the backend can provide trustworthy
price-drop and historical-low data.

# ============================================================ 22. TRACKER AND ACCOUNT

Enable only when backend contracts exist.

Guest capabilities:

- Search.
- View products.
- Compare.
- View history.
- Verify prices.

Authenticated capabilities may include:

- Saved products.
- Price alerts.
- Target prices.
- Recently viewed.
- Search history.
- Notification settings.

Tracker H1:

Track a better price

Guest text:

Create an account to save products and receive price alerts when the
tracker backend is available.

Labels:

- Saved products
- Active price alerts
- Target price
- Current best known price
- Lowest observed price
- Alert status
- Edit alert
- Remove alert
- Pause alert
- Resume alert

Authentication:

- Prefer secure HTTP-only cookies.
- Do not store long-lived tokens in localStorage.
- Frontend guards do not replace backend authorization.
- Feature-flag account navigation.
- Apply appropriate CSRF protections.

# ============================================================ 23. AI ASSISTANT

Do not build a fake chatbot.

Enable only when a real backend endpoint exists.

Route:

/assistant

H1:

Ask Mayabu before you buy

Supporting text:

Describe your budget, use case, preferred specifications, and tradeoffs.
Mayabu will use available product and price data to help you compare.

Examples:

- Best laptop under ₹60,000 for coding
- Should I buy this laptop now or wait?
- Compare iPhone 15 and Samsung Galaxy S23
- Best camera phone under ₹30,000

Answer sections:

- Recommendation
- Why these products
- Tradeoffs
- Current price context
- Sources
- What Mayabu could not verify

Distinguish:

- Backend facts.
- Historical observations.
- Generated recommendations.
- Missing information.
- Uncertain information.

Never fabricate:

- Products.
- Prices.
- Sellers.
- Ratings.
- Specifications.
- Sources.

# ============================================================ 24. SUPPORTED PLATFORMS

Route:

/platforms

Indexing:

index, follow

SEO title:

Supported Ecommerce Platforms | Mayabu

SEO description:

See the Indian ecommerce platforms Mayabu currently supports for
product matching, price comparison, price history, and listing
verification.

H1:

Supported ecommerce platforms

Supporting text:

Mayabu currently compares known product listings from Amazon India,
Flipkart, Croma, and Reliance Digital.

Cards:

- Amazon India
- Flipkart
- Croma
- Reliance Digital

Possible public labels:

- Supported
- Matched listings
- Price observations
- Listing verification
- Last successful data update

Trust notice:

Mayabu is not the seller. Product availability, delivery, coupons, and
checkout totals are controlled by each retailer.

Do not expose:

- Anti-bot internals.
- Proxy data.
- IP addresses.
- Worker counts.
- Internal traces.
- Private breaker information.
- Admin controls.

# ============================================================ 25. HOW IT WORKS

Route:

/how-it-works

Indexing:

index, follow

SEO title:

How Mayabu Product and Price Comparison Works

SEO description:

Learn how Mayabu separates exact products and variants, compares
retailer offers, records price history, and verifies known product
listings.

H1:

How Mayabu helps you compare before buying

Sections:

- Product identity first
- Exact matches and variants stay separate
- Stored prices load quickly
- Price history adds context
- Verification checks known listings
- Seller checkout remains final

Required explanation:

Mayabu first identifies the product and variant, then groups matched
retailer listings. Search results come from stored indexed data. A user
may optionally request a bounded background verification for a known
listing. Mayabu does not launch unlimited scraping from every page view.

# ============================================================ 26. ABOUT PAGE

Route:

/about

SEO title:

About Mayabu | Product and Price Intelligence

SEO description:

Mayabu is building a trusted buying assistant for Indian ecommerce,
beginning with exact electronics matching, price comparison, history,
and verification freshness.

H1:

About Mayabu

Opening:

Mayabu is a product-discovery and price-intelligence platform designed
to help people compare the correct electronics variant before buying.

Mission heading:

Our mission

Mission text:

Make online product research clearer, faster, and more trustworthy by
combining product identity, retailer offers, price history, and
transparent freshness.

Principles heading:

What Mayabu believes

Principles:

- The correct variant matters more than a misleading cheap price.
- Price freshness should be visible, not hidden.
- Users should understand why a product is recommended.
- A scraper failure should never become a fake zero price.
- The retailer's checkout remains the final source for purchase terms.

Scope heading:

Starting with electronics

Scope text:

Mayabu currently focuses on laptops and mobile phones across Amazon
India, Flipkart, Croma, and Reliance Digital. Additional electronics
categories will be added gradually after data quality is proven.

# ============================================================ 27. CONTACT PAGE

Route:

/contact

SEO title:

Contact Mayabu

SEO description:

Contact Mayabu about product-data issues, incorrect matches, retailer
information, partnerships, privacy, or general feedback.

H1:

Contact Mayabu

Supporting text:

Send feedback, report a product-data problem, or ask about Mayabu. Do
not include passwords, payment information, or sensitive account
details.

Fields:

- Name
- Email address
- Topic
- Product URL or Mayabu page
- Message

Topics:

- Incorrect product match
- Incorrect price or availability
- Missing product
- Retailer or partnership enquiry
- Privacy request
- General feedback

Submit:

Send message

Success heading:

Message received

Success text:

Thank you for contacting Mayabu. Your message has been recorded.

Error heading:

Message could not be sent

Error text:

Please check the form and try again. Do not repeatedly submit the same
message.

Do not pretend the form works before an endpoint exists.

# ============================================================ 28. LEGAL PAGES

Create:

- /privacy
- /terms
- /disclaimer

Require legal review before launch.

Do not present generated legal text as legal advice.

Privacy Policy H1:

Privacy Policy

Sections:

- Information Mayabu collects
- How Mayabu uses information
- Anonymous browser identifiers
- Cookies and local storage
- Analytics
- Account information
- Data retention
- Third-party retailer links
- Security
- User choices and rights
- Contact
- Policy changes

Required statement:

Mayabu does not use a user's device or internet connection as a scraping
proxy.

Terms H1:

Terms of Use

Sections:

- Using Mayabu
- Product and price information
- External retailer links
- No purchase contract with Mayabu
- Acceptable use
- Intellectual property
- Service availability
- Disclaimers
- Limitation of liability
- Changes
- Contact

Disclaimer H1:

Price and Availability Disclaimer

Opening:

Mayabu displays stored prices, historical observations, and optional
listing-verification results. A verification timestamp shows when
Mayabu last observed an offer. It does not guarantee that the price,
stock, coupon, delivery eligibility, or checkout total will remain
unchanged.

Required statements:

- Mayabu is not the seller.
- Retailers control listings and checkout terms.
- Prices may differ by location, account, payment method, membership,
  coupon, or delivery address.
- Users should confirm the exact model and checkout amount on the
  retailer website.

# ============================================================ 29. ADMIN FRONTEND

Admin pages are internal.

Requirements:

- Separate layout.
- Feature flag.
- Backend authorization.
- No browser-embedded admin token.
- No public sitemap inclusion.
- noindex, nofollow.
- Confirmation for destructive actions.
- Audit-friendly descriptions.
- Pagination.
- Filters.
- Safe request-ID visibility.

Dashboard metrics:

- Products
- Platform listings
- Price observations
- Verification queue
- Verification success rate
- Shared verification requests
- Average verification time
- Failed jobs
- Dead jobs
- Platform health
- Open anomalies
- Matching reviews

Matching actions:

- Approve merge
- Reject match
- Group as variant
- Send for review
- Save audit note

Verification columns:

- Task ID
- Product
- Listing
- Platform
- State
- Request count
- Attempts
- Duration
- Error category
- Created time
- Started time
- Completed time

Never display:

- Secrets.
- Proxy credentials.
- Tokens.
- Raw full traces.
- Sensitive identifiers without a valid reason.

# ============================================================ 30. API LAYER

Create:

src/lib/api/client.ts
src/lib/api/schemas.ts
src/lib/api/errors.ts
src/lib/api/search.ts
src/lib/api/products.ts
src/lib/api/verification.ts
src/lib/api/price-history.ts
src/lib/api/tracker.ts
src/lib/api/admin.ts

Expected public endpoints:

GET /api/search
GET /api/products/{product_id}
GET /api/products/{product_id}/offers
GET /api/products/{product_id}/similar-variants
GET /api/products/{product_id}/price-history
POST /api/products/{product_id}/verify-price
GET /api/verification-jobs/{task_id}
GET /api/products/{product_id}/verification-status
GET /api/health
GET /api/ready

Confirm actual OpenAPI before integrating optional endpoints.

Rules:

- Generate or maintain types from OpenAPI where practical.
- Validate critical responses with Zod.
- Normalise errors.
- Preserve request IDs.
- Support AbortSignal.
- Set timeouts.
- Retry safe GET requests conservatively.
- Do not retry mutations unless idempotency is guaranteed.
- Treat 429 and 503 as deliberate states.
- Never expose stack traces.
- Never log confidential headers.
- No direct API calls from visual components.

Missing endpoint behaviour:

- Do not crash.
- Hide or disable the feature.
- Keep TODOs in adapters.
- Do not scatter mocks.
- Do not fabricate success.

# ============================================================ 31. TANSTACK QUERY

Key factories:

searchKeys.all
searchKeys.results(params)
categoryKeys.list(category, params)
productKeys.detail(productId)
productKeys.offers(productId)
productKeys.similarVariants(productId)
productKeys.priceHistory(productId, range, platform)
verificationKeys.status(productId)
verificationKeys.job(taskId)

Rules:

- Align stale time with backend freshness.
- Do not refetch everything on window focus.
- Refetch product details after a reasonable interval.
- Isolate verification polling.
- Update caches surgically.
- Never invalidate the entire search cache unnecessarily.
- Seed client cache from SSR data.
- Avoid duplicate hydration requests.
- Do not use misleading price placeholders.
- Browser cache existence does not mean price freshness.

# ============================================================ 32. ERRORS AND RESILIENCE

Handle:

- FastAPI offline.
- Database-dependent endpoint unavailable.
- Redis-dependent verification unavailable.
- Search timeout.
- Product removed.
- Product missing.
- No offers.
- Out of stock.
- Invalid price.
- Invalid MRP.
- Missing image.
- Missing specifications.
- Wrong match.
- Queue full.
- Rate limited.
- Platform blocked.
- Captcha.
- Job expired.
- Partial platform failure.
- Price changed during navigation.
- Browser offline.
- Stale SSR response.
- Hydration mismatch.

Rules:

- One section failure must not crash the page.
- Use route and component boundaries.
- Keep last valid data visible.
- Retry only when useful.
- Avoid endless retries.
- Never replace a valid price with zero.
- Return correct server status codes.
- Do not return HTTP 200 for missing indexable products.

Offline message:

You appear to be offline. Previously loaded information may still be
available.

Retry:

Try again

Section error:

This section could not be loaded.

Page error heading:

Something went wrong

Page error text:

Mayabu could not load this page. Please try again.

404 heading:

Page not found

404 text:

The page may have moved, or the product may no longer be available in
Mayabu's index.

404 action:

Search products

# ============================================================ 33. PERFORMANCE

Targets:

- Lighthouse near 90 or better.
- LCP under 2.5 seconds where practical.
- CLS under 0.1.
- INP under 200 milliseconds where practical.
- Lean initial JavaScript.
- No chart bundle outside chart routes.
- No admin bundle in public entry.

Implementation:

- SSR indexable content.
- Prerender static pages.
- Lazy-load charts.
- Lazy-load admin tables.
- Lazy-load dialogs.
- Lazy-load assistant.
- Optimise images.
- Responsive images.
- Reserve image space.
- Debounce suggestions.
- Cancel obsolete requests.
- Virtualise only large lists.
- Do not render hundreds of cards.
- Avoid expensive render calculations.
- Memoise only after profiling.
- Use content-hashed assets.
- Cache immutable assets.
- Enable compression.
- Run bundle analysis.
- Do not use vite preview as a production server.

# ============================================================ 34. ACCESSIBILITY

Target WCAG 2.2 AA.

Require:

- Semantic landmarks.
- Logical headings.
- Keyboard navigation.
- Visible focus.
- Skip link.
- Form labels.
- Associated validation errors.
- Accessible dialogs.
- Focus trapping.
- Focus restoration.
- Meaningful image alt text.
- Decorative-image handling.
- Sufficient contrast.
- ARIA live status.
- Accessible verification progress.
- No colour-only meaning.
- Reduced motion.
- 44px touch targets.
- Chart text summaries.
- Proper table headers.
- Complete accessible names.

Skip link:

Skip to main content

Never use an icon-only button without an accessible name.

# ============================================================ 35. SECURITY AND PRIVACY

- Never use dangerouslySetInnerHTML for scraped content.
- Escape platform text.
- Validate seller URLs.
- Allow HTTPS and approved local development URLs only.
- Use target blank with rel noopener noreferrer sponsored.
- Never expose secrets.
- Never expose proxy credentials.
- Never expose database credentials.
- Never expose Redis credentials.
- Never expose admin tokens.
- Use Content Security Policy.
- Restrict image origins.
- Avoid sending sensitive queries to third parties.
- Never use user IPs as scraping proxies.
- Never use user devices as scraping proxies.
- Do not fingerprint users.
- Use anonymous client IDs only as expected by the backend.
- Respect analytics consent.
- Do not show internal traces.
- Protect admin routes.
- Protect against open redirects.
- Do not store sensitive data in localStorage.
- Review CORS, cookies, CSRF, Secure, and SameSite behaviour.

Validate every external store link before rendering it.

# ============================================================ 36. SEO REQUIREMENTS

SEO is not a later plugin.

Initial HTML for indexable pages must contain:

- One title.
- Meta description.
- Canonical link.
- Robots directive.
- H1.
- Main content.
- Crawlable links.
- Relevant structured data.

Do not serve an empty app shell for important indexable pages.

Titles:

Home:
Mayabu: Compare Electronics Prices in India

Category:
Compare {Category} Prices and Variants in India | Mayabu

Product:
{Product Name}: Price Comparison and History | Mayabu

About:
About Mayabu | Product and Price Intelligence

Platforms:
Supported Ecommerce Platforms | Mayabu

How it works:
How Mayabu Product and Price Comparison Works

Avoid keyword stuffing.

Do not repeat brand and model unnecessarily.

Descriptions:

- Unique for every indexable page.
- Describe the actual content.
- Do not promise a guaranteed lowest price.
- Do not use one generic description for all products.

Canonicals:

- Include in initial HTML.
- Use absolute HTTPS URLs.
- Include exactly one.
- Use stable product ID and current slug.
- Remove tracking parameters.
- Never canonicalise distinct variants together.
- Redirect duplicate URL forms.
- Put only canonical URLs in sitemaps.

Links:

- Use real anchors with href.
- Do not rely only on click handlers.
- Use descriptive anchor text.
- Link categories to products.
- Link products to categories.
- Link related products.
- Avoid orphan pages.

Robots:

- Create robots.txt.
- Allow required JavaScript and CSS.
- Do not block assets required for rendering.
- Do not block a URL if a crawler must access it to see noindex.
- Restrict internal paths appropriately.

Sitemaps:

Create:

- Sitemap index when needed.
- Static-page sitemap.
- Category sitemap.
- Product sitemap.
- Partitioned product sitemaps when scale requires it.

Include only:

- Canonical URLs.
- Indexable URLs.
- Successful URLs.
- Useful URLs.

Exclude:

- Search queries.
- Filter combinations.
- Sort combinations.
- Compare URLs.
- Admin.
- Account.
- Removed products.
- Verification jobs.

Use absolute URLs.

Use meaningful lastmod values.

Do not update lastmod on every request.

Structured data:

Mayabu is an aggregator and product-intelligence service.

Mayabu is not the merchant completing the sale.

Use Product structured data suitable for product snippets on valid
single-product pages.

Do not claim merchant-listing eligibility.

Use only visible and valid data.

Potential Product properties:

- @type Product
- name
- image
- description
- brand
- model
- mpn when valid
- sku only when valid
- offers or AggregateOffer only when accurately represented
- lowPrice
- highPrice
- offerCount
- priceCurrency INR
- availability when known

Never include:

- Fake ratings.
- Fake reviews.
- Fake GTIN.
- Zero price.
- Expired price presented as current.
- Mayabu shipping terms when Mayabu is not the seller.
- Mayabu return policy as product-seller policy.

Use BreadcrumbList.

Use Organization and WebSite only with accurate information.

Structured data must reflect visible page data.

Place product structured data in initial rendered HTML.

Validate structured data before launch.

Variants:

- Materially different variants receive distinct canonical pages when
  they are distinct backend products.
- Never merge 8GB and 16GB variants for SEO convenience.
- Use product-group relationships only when backend data is reliable.

Images:

- Crawlable image URLs.
- Useful alt text.
- Stable URLs.
- Width and height.
- Modern formats where possible.
- Appropriate social preview size.
- Default Mayabu Open Graph image.

Social metadata:

- og:title
- og:description
- og:url
- og:type
- og:image
- Twitter/X card tags

Do not use an unrelated image.

Search and filters:

- Use consistent parameters.
- Prevent infinite crawl spaces.
- noindex arbitrary search pages.
- noindex or canonicalise filters deliberately.
- Create indexable intent pages only with unique useful content.

HTTP status:

- Valid: 200.
- Permanent redirect: 301 or 308.
- Missing product: 404.
- Permanently removed: 410 when appropriate.
- Temporary backend failure: 5xx.

Do not serve an indexable 200 error page.

Search readiness:

- Search Console verification.
- Sitemap submission.
- URL inspection.
- Core Web Vitals.
- Rich-result validation.
- Crawl-error review.
- Coverage review.

Do not add fake verification tokens.

# ============================================================ 37. ANALYTICS

Use a vendor-neutral privacy-aware abstraction.

Track:

- Search submitted.
- Suggestion selected.
- Result opened.
- Exact match selected.
- Similar variant selected.
- Related product selected.
- Filter applied.
- Sort changed.
- Compare added.
- Compare removed.
- Comparison shared.
- Store link opened.
- Verify best requested.
- Verify all requested.
- Verification joined.
- Verification queued.
- Verification completed.
- Verification failed.
- Price changed.
- Wrong match reported.
- Price issue reported.

Never send:

- Tokens.
- Raw internal errors.
- Admin data.
- Sensitive personal data.
- Full free-text messages.

Respect consent requirements.

# ============================================================ 38. TESTING

Unit tests:

- Price formatting.
- INR formatting.
- Freshness formatting.
- Discount validation.
- Invalid MRP.
- Verification mapping.
- API error normalisation.
- Canonical generation.
- Slug generation.
- Robots policy.
- Structured-data generation.
- Product cards.
- Relationship labels.
- Query keys.
- External URL validation.

Component tests:

- Desktop navbar.
- Mobile menu.
- Footer links.
- Search loading.
- Search empty.
- Search error.
- Partial results.
- Missing product image.
- No offers.
- Verification fresh.
- Verification queued.
- Verification joined.
- Verification running.
- Verification completed.
- Verification failed.
- Verification rate limited.
- Queue full.
- Mobile offer cards.
- Accessible dialogs.
- Compare add and remove.

SSR and SEO tests:

Confirm initial HTML contains:

- Correct title.
- Description.
- Canonical.
- H1.
- Main content.
- Structured data.

Confirm:

- Search is noindex.
- Admin is noindex.
- Missing products return 404.
- Canonical slug redirects work.
- Invalid prices are excluded from schema.
- Fake ratings are absent.
- Sitemap contains canonical URLs only.
- robots.txt allows required assets.

End-to-end:

1. Open home.
2. Search for a laptop.
3. Open exact result.
4. Confirm variants are separate.
5. Compare offers.
6. View history.
7. Start best-price verification.
8. Poll completion.
9. Keep cached price visible while running.
10. Keep cached price after failure.
11. Handle rate limiting.
12. Add comparison products.
13. Copy comparison URL.
14. Report wrong match.
15. Navigate by keyboard.
16. Test mobile.

Use deterministic API fixtures.

Do not use live ecommerce pages in frontend CI tests.

Playwright frontend tests are not production scraping.

# ============================================================ 39. DEVELOPER EXPERIENCE

Provide:

- README.
- .env.example.
- Setup.
- SSR instructions.
- Production build instructions.
- FastAPI integration notes.
- API contract notes.
- Feature flags.
- Testing instructions.
- Accessibility checklist.
- SEO checklist.
- Deployment guidance.
- CORS troubleshooting.
- API URL troubleshooting.
- Hydration troubleshooting.
- Playwright test troubleshooting.

Required scripts:

dev
build
build:client
build:server
prerender
start
preview
lint
typecheck
test
test:coverage
test:e2e
format
format:check
seo:verify

vite preview is for local preview only.

The project must pass:

- Install.
- Client build.
- Server build.
- Prerender.
- TypeScript.
- ESLint.
- Unit tests.
- Component tests.
- E2E tests.
- SEO verification.

# ============================================================ 40. DEPLOYMENT

Deploy independently from FastAPI.

Approved model:

- React + Vite frontend SSR/prerender output on a Node-capable host,
  CDN, or edge-capable platform.
- FastAPI on its own service.
- PostgreSQL on secured infrastructure.
- Redis on secured infrastructure.
- Playwright workers on controlled worker infrastructure.
- HTTPS.
- Explicit CORS origins.
- Trusted proxy headers only behind trusted infrastructure.

Do not assume frontend and backend share a domain.

Support environment-specific API origins.

For authentication across domains, review:

- Cookie domain.
- SameSite.
- Secure.
- CORS.
- CSRF.

Direct navigation to nested routes must work.

Do not return index.html with status 200 for every missing product.

Configure static-host rewrites deliberately.

# ============================================================ 41. BUILD ORDER

Phase 1:

- React + Vite.
- React Router SSR.
- Strict TypeScript.
- Design tokens.
- App shell.
- Navbar.
- Footer.
- Configuration.
- API client.
- Zod.
- TanStack Query.
- Hydration.
- Error boundaries.
- Loading primitives.
- Feature flags.
- SEO utilities.
- Robots.
- Sitemap architecture.

Phase 2:

- Home.
- Categories.
- Search.
- Exact/similar/related sections.
- Cards.
- Product detail.
- Offers.
- History.
- Structured data.
- Canonical URLs.

Phase 3:

- Verify best.
- Verify all.
- Shared-job handling.
- Polling.
- Queue state.
- Rate limit.
- Cooldown.
- Blocked state.
- Price change.
- Accessibility announcements.
- Cache updates.

Phase 4:

- Compare.
- Deals.
- Tracker shell.
- Buying insight.

Phase 5:

- Platforms.
- How it works.
- About.
- Contact.
- Privacy.
- Terms.
- Disclaimer.

Phase 6:

- Admin.
- Matching review.
- Verification jobs.
- Auth.
- Account.
- Tracker backend.
- Assistant.

Phase 7:

- Performance audit.
- Accessibility audit.
- Security review.
- SEO validation.
- Schema validation.
- Sitemap validation.
- Bundle analysis.
- Cross-browser tests.
- Mobile tests.
- E2E completion.
- Staging load test.

# ============================================================ 42. FINAL QUALITY GATES

Do not declare complete unless:

- npm install succeeds.
- npm run build succeeds.
- Client build succeeds.
- SSR build succeeds.
- Prerender succeeds.
- Typecheck succeeds.
- Lint succeeds.
- Unit tests pass.
- Component tests pass.
- E2E tests pass.
- No broken imports.
- No scattered API URLs.
- No mock data on production pages.
- No unjustified TypeScript any.
- No unsafe scraped HTML.
- Prices include freshness where relevant.
- Verification never blocks initial rendering.
- Cached prices remain visible.
- Exact, similar, and related sections remain separate.
- Unsupported features are hidden.
- Mobile works at 320px and above.
- Keyboard works.
- Screen-reader announcements work.
- Indexable routes return meaningful initial HTML.
- Every indexable page has one title.
- Every indexable page has a unique description.
- Every indexable page has one canonical.
- Product schema contains no fabricated data.
- Search and filter index policies are correct.
- Sitemap contains canonical indexable URLs only.
- Removed products return correct statuses.
- Admin exposes no secrets.
- The UI looks like a serious startup product.

# ============================================================ 43. FINAL DELIVERABLES

Deliver:

1. Complete React + Vite frontend.
2. React Router SSR and prerendering.
3. Clear folder structure.
4. Reusable design system.
5. Typed API layer.
6. Search.
7. Category pages.
8. Product details.
9. Offer comparison.
10. Price history.
11. Live verification.
12. Product comparison.
13. Responsive layouts.
14. Loading states.
15. Empty states.
16. Error states.
17. Stale states.
18. Queue states.
19. Rate-limit states.
20. SEO metadata.
21. Canonical utilities.
22. Product structured data.
23. Breadcrumb structured data.
24. robots.txt.
25. XML sitemap generation.
26. Tests.
27. README.
28. Environment example.
29. Accessibility checklist.
30. SEO checklist.
31. Production build with no TypeScript errors.
32. Build report with honest validation results.

Do not redesign Mayabu's backend.

Do not invent unsupported backend behaviour.

Do not hide missing functionality behind fake data.

Do not use Next.js.

Do not treat Playwright as the database.

Build a serious, maintainable, production-grade, SEO-friendly
React + Vite frontend aligned with Mayabu v5.2.

# ============================================================ 44. FINAL IMPLEMENTATION REPORT

At completion, report:

- Frontend stack used.
- Rendering mode.
- FastAPI endpoints integrated.
- Routes implemented.
- Feature-flagged routes.
- SEO features.
- Accessibility features.
- Security protections.
- Tests executed.
- Build commands executed.
- Build results.
- Known limitations.
- Features hidden because backend support is missing.

Do not claim production readiness unless all final quality gates were
actually validated.

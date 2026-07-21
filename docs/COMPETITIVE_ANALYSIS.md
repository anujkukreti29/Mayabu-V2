# Competitive notes for Mayabu

## Competitor patterns observed

### Smartprix / MySmartPrice style

These platforms emphasize large catalogues, structured specs, filters, comparisons, and spec-score style ranking. This means Mayabu cannot win only with a basic price table. The product data must be structured and searchable.

### BuyHatke style

BuyHatke emphasizes price history, price tracking, price alerts, auto coupons, extension-led discovery, and cross-store comparison. This proves that price history and alerts are core retention features, not optional extras.

## Mayabu differentiation

Mayabu should combine both patterns:

1. Structured laptop catalogue like comparison sites.
2. Price history and alerts like tracker products.
3. Conservative exact-variant matching.
4. Buying-assistant answers grounded in Mayabu's own database.
5. Trust UI: last updated, stock status, platform-specific history, and verified match labels.

## Backend implications

The backend must support:

- exact laptop variant extraction;
- cross-platform listing clustering;
- platform-wise price history;
- best market price history;
- manual review queue;
- freshness and scraper health metrics;
- alert-ready daily rollups;
- anomaly detection.

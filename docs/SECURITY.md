# Mayabu security model

## Confidentiality

- Store secrets in `.env` only.
- Never commit production credentials.
- Use `MAYABU_ADMIN_TOKEN` for admin endpoints.
- Hash IP/session identifiers before storing them.
- Do not expose PostgreSQL publicly in production.

## Integrity

- Use parameterized SQL.
- Validate platform URLs before scraping.
- Do not allow public users to submit arbitrary scrape URLs.
- Do not update good price data with `N/A` or invalid prices.
- Use transactions for multi-table updates.

## Availability

- User search reads from DB/cache and does not wait for scrapers.
- Scraper failure records anomalies but API continues serving last-known data.
- Platform health can pause discovery or refresh when blocking appears.

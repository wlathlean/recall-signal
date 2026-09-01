# Recall Signal

Personal-use proof of concept for monitoring U.S. food, pet-food, consumer-product, and vehicle recalls. The dashboard is deployed with Sites; personal watchlist data remains in the browser's local storage.

## Data refresh

`python scripts/update_tracker.py` refreshes `public/data/tracker.json` from official FDA, USDA-FSIS, CPSC, and CDC sources. The GitHub workflow runs at 6:00 AM and 3:00 PM America/Los_Angeles and can also be run manually.

The USDA-FSIS endpoint may deny some automated network locations. The generated dataset records source health explicitly and the dashboard links directly to FSIS whenever that source could not be refreshed.

## Local development

```bash
pnpm install
python scripts/update_tracker.py
pnpm dev
```

No addresses, contact details, VINs, or household watchlist entries are written to the repository or hosted dataset.

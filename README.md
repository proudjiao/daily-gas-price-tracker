# Daily Gas Price Tracker

Fetches the free daily AAA fuel-price average for the Los Angeles-Long Beach metro area and stores it as JSON.

This project uses the Los Angeles-Long Beach metro average as the closest free daily proxy for ZIP code `90048`. AAA does not provide free station-level prices by ZIP code.

## Output

The generated file is:

```text
data/gas_price.json
```

Example shape:

```json
{
  "source": "https://gasprices.aaa.com/?state=CA",
  "zip": "90048",
  "zip_proxy": "90048 -> Los Angeles-Long Beach metro average",
  "metro": "Los Angeles-Long Beach",
  "price_as_of": "5/7/26",
  "fetched_at": "2026-05-07T07:53:05.528134+00:00",
  "prices": {
    "current": {
      "regular": "$6.244",
      "mid_grade": "$6.460",
      "premium": "$6.630",
      "diesel": "$7.532"
    }
  }
}
```

## Run Locally

```bash
python scripts/fetch_gas_price.py
```

No API key or Python dependency install is required.

## Daily Automation

GitHub Actions runs `.github/workflows/daily_gas_price.yml` every day at `15:00 UTC`, which is `8:00 AM Pacific` during daylight saving time.

You can also run it manually from the GitHub repo's **Actions** tab.

## Configuration

Optional environment variables:

- `GAS_PRICE_ZIP`: ZIP metadata stored in the JSON output. Defaults to `90048`.
- `GAS_PRICE_METRO`: AAA metro section to parse. Defaults to `Los Angeles-Long Beach`.
- `GAS_PRICE_ZIP_PROXY`: Human-readable note explaining the ZIP-to-metro proxy.
- `GAS_PRICE_OUTPUT`: Output file path. Defaults to `data/gas_price.json`.

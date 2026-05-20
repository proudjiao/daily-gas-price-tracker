# Daily Gas Price Tracker

Fetches the free daily AAA fuel-price average for the Los Angeles-Long Beach metro area and stores it as JSON.

This project uses the Los Angeles-Long Beach metro average. AAA does not provide free station-level prices.

## Output

The generated file is:

```text
data/gas_price.json
```

Example shape:

```json
{
  "source": "https://gasprices.aaa.com/?state=CA",
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
  },
  "recommendation": {
    "fuel_type": "regular",
    "status": "high",
    "trend": "trending_up",
    "action": "gas_today",
    "summary": "Prices are high and trending up, so filling today is safer if you need gas soon.",
    "reason": "Regular is $0.140 above last week and $0.196 above last month.",
    "comparisons": {
      "vs_yesterday": 0.003,
      "vs_week_ago": 0.14,
      "vs_month_ago": 0.196
    }
  }
}
```

## Recommendation

The recommendation uses regular gas by default. It compares today's price against a price range insight and recent trend direction.

- `low`: current price is below the typical range.
- `typical`: current price is inside the typical range.
- `high`: current price is above the typical range.

The action is `gas_today`, `wait_if_possible`, or `neutral`.

## Price Range Insight

The newsletter includes a Google-style price range bar showing where today's regular price sits relative to observed Los Angeles-Long Beach AAA metro gas prices.

The tracker stores daily observations in:

```text
data/history.json
```

History behavior:

- The active insight uses history mode after at least `14` stored observations.
- Until then, bootstrap mode uses AAA's current, yesterday, week-ago, month-ago, and year-ago comparison points.
- Range labels use the observed minimum, 25th percentile, 75th percentile, and observed maximum.
- The history file is deduped by day and metro, sorted oldest to newest, and pruned to the most recent `3` years so the repo does not grow forever.

## Run Locally

```bash
python scripts/fetch_gas_price.py
```

No API key or Python dependency install is required.

## Manual Automation

GitHub Actions automatic scheduling is disabled. Run `.github/workflows/daily_gas_price.yml` manually from the GitHub repo's **Actions** tab.

## Email Alerts

The workflow can email the daily update through any SMTP account. For Gmail, create an app password and use these GitHub Actions secrets:

- `EMAIL_TO`: Recipient email address.
- `EMAIL_FROM`: Sender email address. Optional; defaults to `SMTP_USERNAME`.
- `SMTP_HOST`: SMTP server, for example `smtp.gmail.com`.
- `SMTP_PORT`: SMTP port, usually `587`.
- `SMTP_USERNAME`: SMTP username, usually your sender email address.
- `SMTP_PASSWORD`: SMTP password or Gmail app password.

Emails are sent as a newsletter-style HTML message with a plain-text fallback. The newsletter includes a recommendation card, fuel price snapshot, colored trend arrows, and a short explanation of how the recommendation is generated.

## Configuration

Optional environment variables:

- `GAS_PRICE_METRO`: AAA metro section to parse. Defaults to `Los Angeles-Long Beach`.
- `GAS_PRICE_OUTPUT`: Output file path. Defaults to `data/gas_price.json`.
- `GAS_PRICE_HISTORY_OUTPUT`: History file path. Defaults to `data/history.json`.

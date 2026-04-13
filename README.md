# Local Side-Work Listing Monitor

This starter app watches local side-work listings and outputs a spreadsheet (`.csv`) while sending alerts for newly discovered posts.

## What it does now
- Polls **Craigslist** job listings via public RSS feeds (by city/region).
- Saves unique listings to SQLite for de-duplication.
- Exports all results to a CSV spreadsheet every poll cycle.
- Sends near-real-time notifications by:
  - Email (SMTP)
  - Text message (Twilio SMS)

## Important platform/ToS note
For platforms like **Facebook** and **Nextdoor**, direct scraping can violate Terms of Service and can get accounts blocked. This project keeps those connectors disabled by default and is designed for approved integrations/export workflows.

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp .env.example .env
python app.py
```

## Configure areas and keywords
Edit `config.yaml`:
- `search.keywords`: terms like `handyman`, `moving`, `yard work`
- `search.craigslist.areas`: e.g. `sfbay`, `sacramento`, `losangeles`
- `poll_interval_seconds`: set to 60 for roughly minute-level checks

## Notification setup
### Email
In `.env`, set:
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`
- `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`

### SMS
In `.env`, set:
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`, `ALERT_SMS_TO`

## Output files
- `listings.db` — local history + dedupe
- `listings.csv` — spreadsheet-compatible output (open in Excel/Google Sheets)

## Suggested next upgrades
- Add a small web dashboard (Flask/FastAPI + frontend)
- Deploy as a background worker on a VPS
- Add additional approved data sources/APIs
- Add unit tests + retries + structured logging

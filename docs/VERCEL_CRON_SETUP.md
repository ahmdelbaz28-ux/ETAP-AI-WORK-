# Vercel Cron Setup & Operational Truth (FIX-37)

## Overview
Vercel Cron triggers the daily engineering email digest via `/api/cron/digest` at `08:00 UTC` daily.

## Security & Authentication
To prevent unauthorized public invocations of `/api/cron/digest`:
- Set the `CRON_SECRET` environment variable in Vercel Project Settings (`Settings -> Environment Variables`).
- Vercel automatically includes `Authorization: Bearer <CRON_SECRET>` with every cron request.
- Unauthenticated requests receive `HTTP 401 Unauthorized`.

## Required Vercel Environment Variables
| Variable | Description |
|---|---|
| `CRON_SECRET` | Secret key used by Vercel to authenticate cron invocations |
| `HF_SPACE_URL` | Base URL of the AhmedETAP Hugging Face Space (`https://ahmdelbaz28-ahmedetap-platform.hf.space`) |
| `ENGINEERING_SERVICE_API_KEY` | API key required by the backend to run study digests |
| `CLOUDFLARE_ORIGIN_SECRET` | Optional origin verification header |

## Schedule
The cron is configured in `vercel.json`:
```json
"crons": [
  {
    "path": "/api/cron/digest",
    "schedule": "0 8 * * *"
  }
]
```
Note: On Vercel Hobby plan, cron executions are limited to once per calendar day.

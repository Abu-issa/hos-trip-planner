# HOS Trip Planner

## Overview

A full-stack trip planning application for property-carrying commercial drivers. It geocodes current, pickup, and dropoff locations, calculates a road route, creates a projected HOS-compliant duty schedule under the stated assumptions, inserts required rest/break/fuel events, and generates projected daily duty-status logs.

**This is a planning/demo application, not a certified ELD system.**

## Live Demo
Frontend: https://hos-trip-planner-gilt.vercel.app/
Backend API: https://hos-trip-planner-vj4z.onrender.com
Replace these placeholders after deployment and production verification.

## Features

- Current → Pickup → Dropoff routing and OpenStreetMap visualization.
- HOS scheduling: 11-hour driving limit, 14-hour driving window, 30-minute break handling, and 10-hour daily rest.
- 70-hour / 8-day cycle usage accounting from supplied aggregate usage.
- One-hour pickup and one-hour dropoff.
- Thirty-minute fueling at least every 1,000 miles when further travel remains.
- Estimated route stop markers and chronological duty timeline.
- Multi-day projected log sheets with four duty statuses and exact-time SVG graphs.
- Responsive UI, accessible form labels, and input/provider error handling.

## Tech Stack

| Area | Technologies |
| --- | --- |
| Backend | Python, Django, Django REST Framework, django-cors-headers, requests, Gunicorn |
| Frontend | React, Vite, Axios, React Leaflet, Leaflet |
| Map/data | OpenStreetMap, Nominatim, OSRM |
| Testing | Django test framework and Python unittest |

## Architecture

The backend validates inputs, geocodes locations, requests two routing legs, schedules duty events, and transforms events into daily logs. The frontend renders the form, route map, trip summary, timeline, and projected daily log visualizations.

```text
backend/
  config/                  Django settings, URLs, WSGI/ASGI
  trips/
    api/                   Validation and API views
    services/
      providers.py         Shared HTTP handling and sanitized errors
      geocoding.py          Cached, throttled location resolution
      routing.py            Two OSRM road-route legs
      hos_engine.py         Network-independent HOS scheduling
      trip_planner.py       Orchestration and response assembly
      daily_logs.py         Schedule-to-daily-log transformation
    tests/                 Provider, API, HOS, log, deployment tests
  gunicorn.conf.py          Single-worker production configuration
frontend/
  src/
    components/            Form, map, summary, timeline, log sheets
    services/              Axios API client
    utils/                 Display formatting
```

`hos_engine.py` is network-independent and directly testable. `daily_logs.py` splits existing events at day boundaries without recalculating HOS or changing the schedule. The app has no persistence, accounts, or database-backed endpoints.

## API

`GET /api/health/` returns HTTP 200 with `{"status":"ok"}`, without contacting providers or a database.

`POST /api/trips/plan/` accepts exactly four JSON fields:

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Indianapolis, IN",
  "dropoff_location": "Dallas, TX",
  "current_cycle_used": 15
}
```

Locations must be nonempty strings, at most 255 characters after trimming. Cycle usage must be a finite JSON number between 0 and 70 inclusive. Numeric strings, booleans, missing fields, and unknown fields are rejected.

| Response section | Contents |
| --- | --- |
| `input` | Normalized four-field request |
| `locations` | Resolved names and coordinates for current, pickup, dropoff |
| `route` | Mileage, driving seconds, and exactly two GeoJSON legs |
| `summary` | Driving/work/elapsed times, cycle values, stop counts, log count |
| `hos` | Planning status, explanation where needed, assumptions |
| `stops` | Activities, estimated coordinates, timing, source event IDs |
| `duty_events` | Ordered statuses, reasons, relative offsets, mileage, leg IDs |
| `daily_logs` | Relative days, clipped entries, totals, mileage, remarks |

GeoJSON uses `[longitude, latitude]`; Leaflet receives `[latitude, longitude]`. Calculations retain fractional seconds; display values are rounded. `remaining_cycle_hours` and `cycle_hours_available_at_start` describe departure capacity.

If all driving, pickup, dropoff, and fuel work cannot fit within remaining known cycle capacity, HTTP 200 returns `hos.status = INSUFFICIENT_CYCLE_HOURS`. The route and required-work explanation remain available; stops, duty events, and logs are empty. This conservative completion policy does not fabricate a partial legal schedule or reconstruct rolling history.

| HTTP status | Meaning |
| --- | --- |
| 400 | Invalid fields or malformed JSON |
| 422 | Unresolved location or no road route |
| 502 | Provider unavailable or malformed response |
| 504 | Provider timeout |

Field errors use DRF field-keyed arrays. Provider errors use `{"error":{"code":"...","message":"...","fields":{}}}`. Raw provider bodies and exceptions are not returned.

## HOS Rules Implemented

- Maximum 11 accumulated driving hours after a qualifying 10-hour rest.
- Driving within a 14-hour elapsed window from first work; ordinary breaks do not extend it.
- A consecutive 30-minute non-driving interval before further driving after eight cumulative driving hours.
- Qualifying pickup/fuel periods satisfy the break without duplication.
- Driving and on-duty-not-driving consume the supplied 70-hour cycle capacity; off-duty and sleeper time do not.
- Ten-hour sleeper rests reset daily driving, break, and window clocks, but not cycle usage.

The four log statuses are Off Duty, Sleeper Berth, Driving, and On Duty (Not Driving). A relative day can include more than 11 driving hours when separated by a qualifying rest; that limit applies between rests, not to midnight-to-midnight totals. See the [FMCSA HOS summary](https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations).

## Assessment Assumptions

- Property-carrying driver; 70-hour / 8-day cycle; no adverse-driving-condition exception or split-sleeper calculation.
- Departure follows at least 10 consecutive hours off duty, with fresh daily clocks.
- `current_cycle_used` is already-consumed cycle usage. Previous eight daily records are not supplied. No invented history, rolling recapture, or automatic 34-hour restart.
- Pickup and dropoff take one on-duty hour each.
- Fueling takes 30 on-duty minutes. Fuel starts full and is replenished at 1,000-mile boundaries while more driving remains; no fueling solely at final arrival.
- Uniform driving speed within each provider leg; estimated stops follow cumulative road geometry.
- Each planning day is 86,400 seconds. Events split at boundaries; driving mileage is allocated proportionally.
- After dropoff, only the final day's remainder becomes projected Off Duty to complete the sheet. Trip duration and cycle usage do not change.

## Important Limitations

1. OSRM provides general driving routes, not commercial truck routing or verified truck restrictions.
2. Generated fuel/rest coordinates are estimated route points, not verified truck stops or legal parking facilities.
3. Public Nominatim/OSRM services can time out, rate limit, or become unavailable. No fabricated route fallback exists.
4. Geocoding uses the first matching result; review resolved names for ambiguous locations.
5. Aggregate cycle usage cannot reconstruct previous eight-day duty history.
6. Logs use relative Day 1 / Day 2 labels, not actual dates or timezones.
7. Projected logs are planning outputs, not certified ELD records.
8. Print CSS exists; physical printing and pagination have not been formally verified.
9. Geocoding cache/throttle are process-local. Use **one worker and one service instance**, without autoscaling. Scaling requires a shared limiter or another provider. Requests are submit-only, cached for 24 hours, and spaced at least 1.1 seconds apart within that process. See [Nominatim's policy](https://operations.osmfoundation.org/policies/nominatim/).

## Running Locally

Use Python 3.12 and Node.js 24 LTS with npm. Start from the repository root.

```sh
cd backend
python -m venv .venv
```

Activate on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```sh
source .venv/bin/activate
```

Then:

```sh
pip install -r requirements.txt
python manage.py check
python manage.py test
python manage.py runserver
```

Backend `.env.example` documents shell variables; Django does **not** automatically load `.env`. Development defaults work without overrides. No migrations are required. Gunicorn is for Linux deployment; Windows local development uses Django's development server.

Frontend, in a second terminal from the repository root:

```sh
cd frontend
npm ci
```

Copy `.env.example` to `.env`: `Copy-Item .env.example .env` on PowerShell, or `cp .env.example .env` on macOS/Linux. Then:

```sh
npm run dev
```

Open `http://127.0.0.1:5173`. Restart Vite after environment changes. Development port 5173 is fixed.

## Environment Variables

Backend variables come from the shell or hosting dashboard:

| Variable | Default / purpose |
| --- | --- |
| `DJANGO_DEBUG` | `true` locally; **set `false` in production** |
| `DJANGO_SECRET_KEY` | Random development key; required when debug is false; keep private |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames, default `localhost,127.0.0.1`; no scheme/path |
| `CORS_ALLOWED_ORIGINS` | Exact comma-separated origins; defaults to localhost/127.0.0.1 port 5173 |
| `NOMINATIM_URL` | `https://nominatim.openstreetmap.org/search` |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` |
| `PROVIDER_USER_AGENT` | Development identifier; use a descriptive production identifier with project/contact URL |
| `PROVIDER_TIMEOUT_SECONDS` | Read timeout, default `10`; connection timeout is 3.05 seconds |
| `DJANGO_TRUST_PROXY` | `false`; enable only behind a trusted proxy that overwrites `X-Forwarded-Proto` |
| `DJANGO_SECURE_SSL_REDIRECT` | Defaults to true when debug is false; optional boolean override |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` initially; optionally `3600` after HTTPS verification |
| `PORT` | Gunicorn port supplied by Render; local default `8000` |

Use `true`/`false` for booleans. Production cookie security is enabled automatically. Framing is denied; HSTS subdomains/preload remain disabled.

Frontend:

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | Backend origin; locally `http://localhost:8000`; on Vercel the actual HTTPS backend origin |

Vite variables are public, embedded at build time, and must never contain secrets. Without an API URL, production uses same-origin requests; separate Vercel/Render hosting **requires** `VITE_API_BASE_URL`. There is no production localhost fallback. Rebuild after changing this value.

## Testing

Current verification: **61 backend tests pass**, including 57 correctness tests and four deployment/security tests. Coverage includes validation, providers, HOS boundaries, cycle limits, fuel scheduling, daily-log splitting, mileage conservation, API integration, proxy/CORS behavior, and edge cases. A deterministic 200-case schedule matrix checks invariants. Automated provider requests are mocked; tests need no database or internet.

`python manage.py check`, `python manage.py test` (from backend), and `npm run build` (from frontend) pass. No frontend automated test suite exists. Browser verification covered live short/long routes, insufficient capacity, invalid locations, controlled timeout handling, coincident markers, mobile layout, and exact-time graph rendering.

Production-like `python manage.py check --deploy` reports the intentional HSTS warning with HSTS disabled. With HSTS 3600 it instead warns about disabled subdomains/preload; those are deliberately not enabled for an assessment domain. WSGI import/configuration passed; actual Gunicorn startup still needs Linux verification because this preparation environment has no working Linux runtime.

## Example

Enter **Chicago, IL → Indianapolis, IN → Dallas, TX**, with **15** current cycle hours used. The app generates two route legs, pickup work, required rest scheduling, fuel where required, dropoff, and projected daily logs. Provider estimates can change; the UI shows the current calculation.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for exact GitHub, Render, and Vercel steps, environment values, security decisions, and production verification. Deployment and repository push have not been performed.

# Deployment guide

Use **Render for Django** and **Vercel for React/Vite**. These are manual instructions; no deployment or push has been performed. Replace all `<PLACEHOLDERS>` before executing commands.

## 1. GitHub

Suggested name: `hos-trip-planner`

Description: Full-stack HOS trip planner built with Django and React, featuring route mapping, FMCSA-based scheduling, and projected daily duty logs.

Create an empty GitHub repository under your account, choosing assessment-appropriate visibility. Do not initialize another README or gitignore. From the local repository root:

```sh
git status --short
git status --short --ignored
git add .
git diff --cached --stat
git diff --cached
git commit -m "Complete HOS trip planner assessment"
git branch -M main
git remote add origin https://github.com/<GITHUB_USER>/hos-trip-planner.git
git push -u origin main
```

Review the staged diff before committing. Include source, tests, documentation, dependency manifests/lockfiles, and `.env.example` files only. Never include actual secrets, environments, dependency directories, or generated builds. There is currently no remote; if one is added later, inspect `git remote -v` before changing it. These commands are for the user to execute when ready.

## 2. Render backend

Create a Python **Web Service**, connect the repository, and configure:

| Setting | Value |
| --- | --- |
| Branch | `main` |
| Root directory | `backend` |
| Runtime | Python |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn --config gunicorn.conf.py config.wsgi:application` |
| Health check | `/api/health/` |
| Instances | **1**, autoscaling disabled |

Choose an appropriate instance plan after reviewing current pricing and idle behavior. An always-on instance avoids cold-start delays during review.

The checked-in Gunicorn config binds to `0.0.0.0:$PORT`, uses **one worker with four threads**, and sets a 120-second worker timeout. Threads share the geocoder lock/cache and allow health requests while a provider call is waiting. Do not override worker count or run multiple service instances. No migrations, database, persistent disk, `collectstatic`, or WhiteNoise are required for this API-only application.

Set these environment variables before deploying:

| Variable | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.12.14` (verified locally; consumed by Render) |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | Newly generated private random secret |
| `DJANGO_ALLOWED_HOSTS` | Actual `<SERVICE>.onrender.com` hostname, without scheme/path |
| `CORS_ALLOWED_ORIGINS` | Empty until frontend exists; then exact `https://<PROJECT>.vercel.app` |
| `DJANGO_TRUST_PROXY` | `true` behind Render's trusted HTTPS proxy |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` initially |
| `NOMINATIM_URL` | `https://nominatim.openstreetmap.org/search` |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` |
| `PROVIDER_USER_AGENT` | `HOSTripPlannerAssessment/1.0 (+https://github.com/<GITHUB_USER>/hos-trip-planner)` |
| `PROVIDER_TIMEOUT_SECONDS` | `10` |

Render supplies `PORT`. Use the actual assigned hostname, including any generated suffix. Generate a secret locally and paste it only into the hosting secret value:

```sh
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Do not commit or screenshot the generated value.

### Security decisions

- Production requires a secret and explicitly disables debug. Hosts and CORS use exact allowlists, never wildcards.
- HTTPS redirection and secure cookie flags are enabled in production. Proxy trust is opt-in and assumes the proxy overwrites incoming `X-Forwarded-Proto`. Do not expose Gunicorn directly to untrusted clients with proxy trust enabled.
- Django sends `X-Frame-Options: DENY`.
- CSRF middleware protects ordinary Django views. The public DRF JSON API has no cookie/session authentication and remains CSRF-exempt. CORS is not authentication or abuse prevention.
- HSTS starts at zero until HTTPS is verified. Optionally set `DJANGO_SECURE_HSTS_SECONDS=3600` afterward and restart. Subdomains and preload remain disabled for this temporary assessment domain.
- Initially `check --deploy` reports `security.W004`. With positive HSTS it reports `security.W005` and `security.W021`, reflecting the deliberate absence of subdomain/preload policies. No warnings are silenced.
- Nominatim's limiter is process-local. Use one process/instance and low-volume demo traffic. Scaling needs a shared limiter/provider change. Avoid simultaneous active copies during redeployment verification.

## 3. Backend startup and health

Deploy after saving settings. Inspect Render logs for the bound port and **one worker**. On Linux with production variables, or a Render shell if available:

```sh
python manage.py check
python manage.py test
python manage.py check --deploy
gunicorn --config gunicorn.conf.py --check-config config.wsgi:application
```

Do not start a second server in the running service shell. For a separate Linux smoke test, run the normal start command. Gunicorn cannot start natively on Windows: preparation encountered the missing Unix `fcntl` module. WSL was unavailable and Docker's Linux engine was not usable. The WSGI callable/configuration were verified separately; actual Linux worker startup remains a deployment gate.

Open the health URL or run:

```sh
curl -i https://<SERVICE>.onrender.com/api/health/
```

Expected: HTTP 200, `{"status":"ok"}`, and `X-Frame-Options: DENY`. There must be no redirect loop. A 400 suggests incorrect allowed hosts; redirect loops suggest a proxy/HTTPS mismatch. Health does not prove mapping-provider availability.

## 4. Vercel frontend

1. Import the same GitHub repository.
2. Choose **Vite**, root directory **frontend**, and Node.js **24.x**.
3. Install command: `npm ci`. Build command: `npm run build`. Output directory: `dist`.
4. Set Production variable `VITE_API_BASE_URL=https://<SERVICE>.onrender.com` before building. Use the origin without `/api` or a trailing slash.
5. Deploy and record the final stable Vercel URL.

No client-side page routing rewrite or Vercel functions are needed. Requests go directly to Render. If the API URL is missing, production uses the frontend origin and requests fail on Vercel; it does not use localhost. Vite embeds public configuration at build time: environment changes require a **new frontend deployment**. Never put secrets in Vite variables.

## 5. Final CORS and restart

1. Set Render's `CORS_ALLOWED_ORIGINS` to the exact stable Vercel origin, without a path/trailing slash.
2. Save and restart/redeploy the backend. Do not put the frontend hostname into `DJANGO_ALLOWED_HOSTS`; that setting describes backend request hosts.
3. Additional intentional frontend origins can be comma-separated. Do not broadly allow all Vercel preview domains. Configure an exact preview origin only when intentionally testing it.
4. Verify OPTIONS and POST requests from the actual frontend. Example preflight:

```sh
curl -i -X OPTIONS https://<SERVICE>.onrender.com/api/trips/plan/ -H "Origin: https://<PROJECT>.vercel.app" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type"
```

Expected: successful response with `Access-Control-Allow-Origin` matching that exact origin. Unrelated origins must not receive that allow header.

## 6. Final production checklist

- [ ] HTTPS health returns 200 without redirect loops.
- [ ] Chicago, IL → Indianapolis, IN → Dallas, TX / cycle **15**: route, timeline, stops, daily logs.
- [ ] New York, NY → Columbus, OH → Los Angeles, CA / cycle **0**: compliant multi-day schedule when provider estimates fit available capacity; multiple rests/logs.
- [ ] Same long route / cycle **65**: insufficient-cycle explanation; map retained, no schedule/logs.
- [ ] Invalid location: friendly errors, retained inputs, no stale results.
- [ ] Mobile: no page overflow; graphs scroll horizontally.
- [ ] Console/network: no application errors, broken assets, CORS errors, mixed content, or localhost requests.
- [ ] Logs: 24 hours each, four rows, correct day transitions, final-day post-trip off duty only.
- [ ] Stops: timeline correspondence, distinguishable original markers, visible map attribution.
- [ ] Provider failures remain sanitized; timeouts do not count as successful route verification. Retry later without inventing routes.
- [ ] One Gunicorn worker/instance confirmed; production logs checked for unexpected tracebacks.
- [ ] Replace README URL placeholders after all checks pass.

## Official references

- [Render Django deployment](https://render.com/docs/deploy-django)
- [Render Python version](https://render.com/docs/python-version)
- [Render health checks](https://render.com/docs/health-checks)
- [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite)
- [Django proxy/security settings](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header)
- [Gunicorn](https://gunicorn.org/)

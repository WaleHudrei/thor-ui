# thor-ui

Unified frontend for the Thor scraper ecosystem. A standalone Railway service that talks to individual scraper services (`thor-mycase`, `thor-sri`, future ones) over HTTP.

**Part of the Thor ecosystem:**
- `thor-mycase` — MyCase scraper (existing)
- `thor-sri` — SRI scraper (existing)
- **`thor-ui`** — unified frontend (this repo)
- Shared Railway Postgres

**What this service does:**
- Serves the sidebar, scraper picker, per-scraper forms
- Proxies API calls to scraper services (keeps URLs server-side)
- Aggregates job history and leads across scrapers
- Provides basic auth to gate access

**What this service does NOT do:**
- No scraping logic — scraper services own that
- No direct DB writes — only reads for the leads browser
- No scraper-specific state — if a scraper goes offline, its page shows "offline"

---

## Files

```
thor-ui/
├── app.py                       Flask routes, proxy logic, auth
├── static/
│   ├── css/thor.css             Design system
│   ├── js/thor.js               Sidebar + shared helpers
│   ├── login.html
│   ├── picker.html              Main scraper picker page (landing)
│   ├── jobs.html                Cross-scraper job history
│   ├── leads.html               Cross-scraper leads browser
│   ├── dashboard.html           Scraper health + recent jobs
│   └── forms/
│       ├── mycase_form.html     MyCase config form + live progress
│       └── sri_form.html        SRI config form + live progress
├── Dockerfile
├── railway.toml
├── requirements.txt
└── .env.example
```

---

## Deployment

### 1. Create Railway service

```bash
cd thor-ui
git init && git add . && git commit -m "thor-ui v1.0"
git remote add origin git@github.com:WaleHudrei/thor-ui.git
git push -u origin main
```

Railway dashboard → New Project → Deploy from GitHub → pick `thor-ui`.

### 2. Set environment variables

| Variable | Value |
|---|---|
| `THOR_MYCASE_URL` | `https://hudrei-scraper-production.up.railway.app` |
| `THOR_SRI_URL` | `https://thor-sri-production.up.railway.app` |
| `APP_PASSWORD` | any strong password |
| `SECRET_KEY` | any random 32-char string (generate with `openssl rand -hex 32`) |

### 3. Verify

```bash
curl https://thor-ui-production.up.railway.app/api/health
```

Should return:
```json
{
  "status": "ok",
  "service": "thor-ui",
  "auth_enabled": true,
  "scrapers_configured": { "mycase": true, "sri": true }
}
```

Then visit `https://thor-ui-production.up.railway.app/` in a browser → login page.

---

## Adding a new scraper

Three steps:

**1.** Register it in `app.py` (add an entry to `SCRAPERS` dict):
```python
SCRAPERS["recorder"] = {
    "name": "County Recorder",
    "description": "Liens, deeds, judgments from Indiana counties",
    "icon": "📜",
    "url": os.getenv("THOR_RECORDER_URL", ""),
    "form_template": "recorder_form.html",
    "enabled": bool(os.getenv("THOR_RECORDER_URL")),
}
```

**2.** Create the form template in `static/forms/recorder_form.html` (copy `sri_form.html` as starting point, adjust fields).

**3.** Set `THOR_RECORDER_URL` env var in Railway.

That's it — the picker will show the new card, the form will work, jobs + leads will aggregate automatically.

---

## Migration from current thor-mycase UI

Phase 2 lets you migrate gradually:

1. **Now:** Deploy thor-ui with `THOR_MYCASE_URL` pointing at the existing thor-mycase service.
2. **Now:** Use thor-ui for all new work; old thor-mycase URL still works too.
3. **Later (Phase 3):** Strip UI from thor-mycase, make it API-only. thor-ui becomes the only frontend.

Zero breakage risk during the transition — both URLs serve the same MyCase scraper.

---

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — point at your local/deployed scrapers
export $(grep -v '^#' .env | xargs)
python app.py
# Visit http://localhost:5000
```

---

## Architecture notes

**Why proxy scraper API calls through thor-ui instead of calling scrapers directly from browser?**
Three reasons:
1. Keeps scraper URLs private (server-side env vars, never in browser JS)
2. No CORS configuration needed on each scraper
3. Centralized auth — one login, all scrapers

**Why separate Railway services instead of one monolith?**
Full process isolation. A bug/crash/deploy in one scraper does not affect the others. Each scraper has its own restart lifecycle, own resource limits, own logs.

**Why read leads through HTTP instead of querying Postgres directly?**
Each scraper owns its schema. If SRI changes its columns, thor-ui does not need to be redeployed — the scraper's `/api/leads` endpoint handles the new shape. Loose coupling.

"""
thor-ui — Unified Thor frontend.

Serves the sidebar, scraper picker, per-scraper forms, job history, and
leads browser. Talks to individual scraper services (thor-mycase, thor-sri)
over HTTP via the contract defined in CONTRIBUTING.md of each scraper.

Queries the shared Postgres directly for cross-scraper dashboards.
"""

import logging
import os
import sys
import time
from functools import wraps
from urllib.parse import urljoin

import requests
from flask import (Flask, Response, jsonify, redirect, request,
                   send_from_directory, session, url_for)
from flask_cors import CORS

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("thor-ui")

# ── App ───────────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.getenv("SECRET_KEY", os.urandom(32).hex())
CORS(app)

SERVICE_START = time.time()

# ── Scraper registry (env-driven) ────────────────────────────────────────────
# Each entry points to a thor-* scraper service. Adding a new scraper means
# adding one entry here + one template in static/forms/.
SCRAPERS = {
    "mycase": {
        "name": "MyCase",
        "description": "Indiana court filings — evictions, foreclosures, small claims, probate",
        "icon": "⚖",
        "url": os.getenv("THOR_MYCASE_URL", ""),
        "form_template": "mycase_form.html",
        "enabled": bool(os.getenv("THOR_MYCASE_URL")),
    },
    "sri": {
        "name": "SRI Services",
        "description": "Indiana tax, commissioner, and sheriff sale auctions",
        "icon": "🏛",
        "url": os.getenv("THOR_SRI_URL", ""),
        "form_template": "sri_form.html",
        "enabled": bool(os.getenv("THOR_SRI_URL")),
    },
}

# ── Basic auth ────────────────────────────────────────────────────────────────
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
AUTH_ENABLED = bool(APP_PASSWORD)
log.info("Auth: %s", "ENABLED" if AUTH_ENABLED else "DISABLED (no APP_PASSWORD set)")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        if session.get("authed"):
            return f(*args, **kwargs)
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("login_page", next=request.path))
    return wrapper


# ── Scraper HTTP client ──────────────────────────────────────────────────────
class ScraperClient:
    """Thin wrapper around requests for calling scraper services."""
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def _url(self, scraper_key: str, path: str) -> str:
        base = SCRAPERS.get(scraper_key, {}).get("url")
        if not base:
            raise ValueError(f"Scraper '{scraper_key}' has no URL configured")
        return urljoin(base.rstrip("/") + "/", path.lstrip("/"))

    def health(self, scraper_key: str) -> dict:
        r = requests.get(self._url(scraper_key, "api/health"),
                         timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def start_scrape(self, scraper_key: str, params: dict) -> tuple[int, dict]:
        r = requests.post(
            self._url(scraper_key, "api/scrape"),
            json={"params": params},
            timeout=self.timeout,
        )
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"error": "invalid_response", "body": r.text}

    def get_job(self, scraper_key: str, job_id: str) -> tuple[int, dict]:
        r = requests.get(self._url(scraper_key, f"api/jobs/{job_id}"),
                         timeout=self.timeout)
        return r.status_code, (r.json() if r.content else {})

    def get_logs(self, scraper_key: str, job_id: str, since: int = 0):
        r = requests.get(
            self._url(scraper_key, f"api/jobs/{job_id}/logs"),
            params={"since": since}, timeout=self.timeout,
        )
        return r.status_code, (r.json() if r.content else {})

    def cancel_job(self, scraper_key: str, job_id: str):
        r = requests.post(self._url(scraper_key, f"api/jobs/{job_id}/cancel"),
                          timeout=self.timeout)
        return r.status_code, (r.json() if r.content else {})

    def history(self, scraper_key: str, limit: int = 50):
        r = requests.get(self._url(scraper_key, "api/jobs/history"),
                         params={"limit": limit}, timeout=self.timeout)
        return r.status_code, (r.json() if r.content else {})

    def leads(self, scraper_key: str, **filters):
        r = requests.get(self._url(scraper_key, "api/leads"),
                         params=filters, timeout=self.timeout)
        return r.status_code, (r.json() if r.content else {})


client = ScraperClient()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if not AUTH_ENABLED:
        return redirect(url_for("scraper_picker"))

    if request.method == "POST":
        pw = (request.form.get("password") or "").strip()
        if pw == APP_PASSWORD:
            session["authed"] = True
            next_url = request.args.get("next") or url_for("scraper_picker")
            return redirect(next_url)
        return send_from_directory("static", "login.html")
    return send_from_directory("static", "login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/")
@login_required
def scraper_picker():
    return send_from_directory("static", "picker.html")


@app.route("/scraper/<scraper_key>")
@login_required
def scraper_form(scraper_key):
    s = SCRAPERS.get(scraper_key)
    if not s or not s["enabled"]:
        return redirect(url_for("scraper_picker"))
    return send_from_directory("static/forms", s["form_template"])


@app.route("/jobs")
@login_required
def jobs_page():
    return send_from_directory("static", "jobs.html")


@app.route("/leads")
@login_required
def leads_page():
    return send_from_directory("static", "leads.html")


@app.route("/dashboard")
@login_required
def dashboard_page():
    return send_from_directory("static", "dashboard.html")


# ══════════════════════════════════════════════════════════════════════════════
# API PROXY ROUTES
# The UI's JS calls these; they forward to the appropriate scraper service.
# This keeps scraper URLs server-side only (cleaner + no CORS headaches).
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/scrapers")
@login_required
def api_scrapers():
    """Public registry + live health check for each scraper."""
    out = {}
    for key, s in SCRAPERS.items():
        entry = {k: v for k, v in s.items() if k != "url"}  # don't leak URL
        if s["enabled"]:
            try:
                entry["health"] = client.health(key)
                entry["online"] = True
            except Exception as e:
                entry["online"] = False
                entry["error"] = str(e)
        else:
            entry["online"] = False
        out[key] = entry
    return jsonify({"scrapers": out})


@app.post("/api/scrape/<scraper_key>")
@login_required
def api_scrape(scraper_key):
    if scraper_key not in SCRAPERS or not SCRAPERS[scraper_key]["enabled"]:
        return jsonify({"error": "scraper_not_found"}), 404
    body = request.get_json(silent=True) or {}
    params = body.get("params") or body
    try:
        status, data = client.start_scrape(scraper_key, params)
        return jsonify(data), status
    except Exception as e:
        return jsonify({"error": "scraper_unreachable", "detail": str(e)}), 502


@app.get("/api/scrape/<scraper_key>/jobs/<job_id>")
@login_required
def api_job(scraper_key, job_id):
    try:
        status, data = client.get_job(scraper_key, job_id)
        return jsonify(data), status
    except Exception as e:
        return jsonify({"error": "scraper_unreachable", "detail": str(e)}), 502


@app.get("/api/scrape/<scraper_key>/jobs/<job_id>/logs")
@login_required
def api_logs(scraper_key, job_id):
    since = request.args.get("since", "0")
    try:
        status, data = client.get_logs(scraper_key, job_id, since=int(since))
        return jsonify(data), status
    except Exception as e:
        return jsonify({"error": "scraper_unreachable", "detail": str(e)}), 502


@app.post("/api/scrape/<scraper_key>/jobs/<job_id>/cancel")
@login_required
def api_cancel(scraper_key, job_id):
    try:
        status, data = client.cancel_job(scraper_key, job_id)
        return jsonify(data), status
    except Exception as e:
        return jsonify({"error": "scraper_unreachable", "detail": str(e)}), 502


@app.get("/api/jobs/history")
@login_required
def api_history():
    """Aggregated history across all enabled scrapers."""
    limit = min(int(request.args.get("limit", "50")), 200)
    scraper_filter = request.args.get("scraper")  # optional filter

    aggregated = []
    for key, s in SCRAPERS.items():
        if not s["enabled"]:
            continue
        if scraper_filter and key != scraper_filter:
            continue
        try:
            status, data = client.history(key, limit=limit)
            if status == 200:
                for job in data.get("jobs", []):
                    job["_scraper"] = key
                    job["_scraper_name"] = s["name"]
                    aggregated.append(job)
        except Exception as e:
            log.warning("history fetch failed for %s: %s", key, e)

    # Sort by created_at desc
    aggregated.sort(key=lambda j: j.get("created_at") or "", reverse=True)
    return jsonify({"jobs": aggregated[:limit]})


@app.get("/api/leads")
@login_required
def api_leads():
    """
    Cross-scraper leads browser. Queries each scraper's /api/leads and
    aggregates. Pass ?scraper=sri to filter.
    """
    scraper_filter = request.args.get("scraper")
    filters = {k: v for k, v in request.args.items() if k != "scraper"}

    aggregated = []
    total = 0
    for key, s in SCRAPERS.items():
        if not s["enabled"]:
            continue
        if scraper_filter and key != scraper_filter:
            continue
        try:
            status, data = client.leads(key, **filters)
            if status == 200:
                total += data.get("total", 0)
                for lead in data.get("leads", []):
                    lead["_scraper"] = key
                    lead["_scraper_name"] = s["name"]
                    aggregated.append(lead)
        except Exception as e:
            log.warning("leads fetch failed for %s: %s", key, e)

    return jsonify({"total": total, "leads": aggregated})


@app.get("/api/health")
def api_health():
    """Health of thor-ui itself (not behind auth)."""
    return jsonify({
        "status": "ok",
        "service": "thor-ui",
        "uptime_seconds": int(time.time() - SERVICE_START),
        "auth_enabled": AUTH_ENABLED,
        "scrapers_configured": {k: s["enabled"] for k, s in SCRAPERS.items()},
    })


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)

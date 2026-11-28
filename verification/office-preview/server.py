"""Public-data-only, disposable read-only preview. No broker or model credentials."""
import datetime as dt
import json
import math
import os
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
TREASURY = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value="
GITHUB = "https://api.github.com/repos/ringoincidents/quantrade"
MAX_BODY = 2_000_000
CACHE_SECONDS = 900
LOCK = threading.Lock()
CACHE = None
LAST_ATTEMPT = -CACHE_SECONDS

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch(url):
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "QuanTrade-public-preview/0.1", "Accept": "*/*"})
    with opener.open(req, timeout=8) as response:
        if response.status != 200:
            raise ValueError("http")
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError("size")
        return body

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def parse_rates(raw, today):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("unsafe xml")
    root = ET.fromstring(raw)
    ns = {"m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
          "d": "http://schemas.microsoft.com/ado/2007/08/dataservices"}
    rows = []
    for props in root.findall(".//m:properties", ns):
        date = dt.date.fromisoformat(props.findtext("d:NEW_DATE", "", ns)[:10])
        if date > today:
            continue
        values = {}
        for label, field in [("2Y","BC_2YEAR"),("10Y","BC_10YEAR"),("30Y","BC_30YEAR")]:
            val = props.findtext("d:" + field, "", ns)
            if val:
                n = float(val)
                if not math.isfinite(n) or not -10 <= n <= 30:
                    raise ValueError("invalid rate")
                values[label] = n
        if len(values) == 3:
            rows.append({"date": date.isoformat(), "rates": values})
    if not rows:
        raise ValueError("no observations")
    rows.sort(key=lambda x: x["date"])
    if len({r["date"] for r in rows}) != len(rows):
        raise ValueError("duplicate observations")
    return rows[-2:]

def issue_state(raw):
    value = json.loads(raw)
    if value.get("number") != 142 or value.get("state") not in ("open", "closed"):
        raise ValueError("issue schema")
    return {"state": value["state"], "updated": value.get("updated_at")}

def pr_state(raw):
    value = json.loads(raw)
    if value.get("number") != 141 or value.get("state") not in ("open", "closed") or type(value.get("draft")) is not bool:
        raise ValueError("pr schema")
    return {"state": value["state"], "draft": value["draft"], "updated": value.get("updated_at")}

def observe():
    today = dt.datetime.now(ZoneInfo("America/New_York")).date()
    result = {"checked_at": now(), "market": None, "issue": None, "pr": None,
              "mode": "PUBLIC_PREVIEW", "broker": "HISTORICAL_READ_VERIFIED"}
    try:
        rows = parse_rates(fetch(TREASURY + str(today.year)), today)
        result["market"] = {"latest": rows[-1], "previous": rows[-2] if len(rows)>1 else None,
                            "age_days": (today-dt.date.fromisoformat(rows[-1]["date"])).days}
    except Exception:
        pass
    for key, path, parse in [("issue","/issues/142",issue_state),("pr","/pulls/141",pr_state)]:
        try:
            result[key] = parse(fetch(GITHUB + path))
        except Exception:
            pass
    return result

def snapshot():
    global CACHE, LAST_ATTEMPT
    with LOCK:
        if CACHE is None or time.monotonic() - LAST_ATTEMPT >= CACHE_SECONDS:
            LAST_ATTEMPT = time.monotonic()
            CACHE = observe()
            print(json.dumps({"market": "PASS" if CACHE["market"] else "UNAVAILABLE",
                              "market_date": CACHE["market"]["latest"]["date"] if CACHE["market"] else None,
                              "issue": "PASS" if CACHE["issue"] else "UNAVAILABLE",
                              "pr": "PASS" if CACHE["pr"] else "UNAVAILABLE",
                              "checked_at": CACHE["checked_at"]}), flush=True)
        return CACHE

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        if self.path == "/":
            body = (ROOT / "index.html").read_bytes()
            kind = "text/html; charset=utf-8"
        elif self.path == "/api/status":
            body = json.dumps(snapshot(), allow_nan=False).encode()
            kind = "application/json"
        elif self.path == "/health":
            body, kind = b"ok", "text/plain"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        self.send_error(405)

if __name__ == "__main__":
    # Warm once before listening; no repeat jobs, cache refresh only on request.
    snapshot()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()

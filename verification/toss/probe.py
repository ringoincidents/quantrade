"""Bounded one-shot, no broker mutations except OAuth token issuance.
Never log secrets, account identifiers, balances, order data or raw errors.
No database, no scheduling, no order creation/cancellation/modification.
"""
import json
import os
import ssl
import sys
from decimal import Decimal
from urllib.parse import urlsplit, unquote

import requests
import websocket

IP = "141.164.41.178"
PORT = 3128
BASE = "https://openapi.tossinvest.com"
WS = "wss://openapi-ws.tossinvest.com/ws/v1"
GETS = {"/api/v1/accounts", "/api/v1/holdings", "/api/v1/buying-power",
        "/api/v1/orders", "/api/v1/sellable-quantity", "/api/v1/exchange-rate"}
MAX_BYTES = 2_000_000

class Blocked(Exception):
    pass

def emit(stage, status):
    print(json.dumps({"stage": stage, "status": status}, separators=(",", ":")), flush=True)

def proxy_config(url):
    p = urlsplit(url)
    if (p.scheme != "http" or p.hostname != IP or p.port != PORT or
            not p.username or not p.password or p.path not in ("", "/") or
            p.query or p.fragment):
        raise Blocked("PROXY_CONFIGURATION_INVALID")
    return p

def request(session, method, path, **kw):
    if path == "EGRESS" and method == "GET":
        url = "https://api.ipify.org"
    elif (method == "GET" and path in GETS) or (method == "POST" and path == "/oauth2/token"):
        url = BASE + path
    else:
        raise Blocked("METHOD_NOT_ALLOWED")
    with session.request(method, url, timeout=(8, 12), allow_redirects=False,
                         stream=True, **kw) as r:
        if r.status_code != 200:
            raise Blocked("HTTP_" + str(r.status_code))
        chunks = bytearray()
        for chunk in r.iter_content(16384):
            chunks.extend(chunk)
            if len(chunks) > MAX_BYTES:
                raise Blocked("RESPONSE_TOO_LARGE")
        return chunks.decode("utf-8") if path == "EGRESS" else json.loads(chunks)

def get(session, token, path, account=None, params=None):
    headers = {"Authorization": "Bearer " + token}
    if account is not None:
        headers["X-Tossinvest-Account"] = account
    return request(session, "GET", path, headers=headers, params=params)["result"]

def finite(value):
    return Decimal(str(value)).is_finite()

def holdings_ok(value):
    return (isinstance(value, dict) and isinstance(value.get("items"), list) and
            all(isinstance(row, dict) and bool(row.get("symbol")) and
                row.get("currency") in ("KRW", "USD") and finite(row["quantity"]) and
                finite(row["lastPrice"]) and finite(row["marketValue"]["amount"])
                for row in value["items"]))

def page_complete(value):
    return value.get("hasNext") in (False, None) and not value.get("nextCursor")

def subscription_status(ack, accounts):
    # Official connection guide: type=subscriptions, top-level subscribed/rejected.
    if not isinstance(ack, dict) or ack.get("type") != "subscriptions":
        raise Blocked("ACK_NOT_RECEIVED")
    subscribed = ack.get("subscribed")
    rejected = ack.get("rejected")
    if (not isinstance(subscribed, list) or not all(isinstance(x, str) for x in subscribed)
            or not isinstance(rejected, list) or not all(isinstance(x, dict) for x in rejected)):
        raise Blocked("ACK_SCHEMA_UNVERIFIED")
    wanted = {"personal:order:" + account for account in accounts}
    actual = set(subscribed)
    order = "PASS" if wanted <= actual else "PARTIAL" if wanted & actual else "NOT_CONFIRMED"
    market = "PASS" if "trade:us:AAPL" in actual else "NOT_CONFIRMED"
    return order, market

def ws_check(proxy, token, accounts):
    # Explicit authenticated HTTP CONNECT tunnel, TLS validation, no trace.
    conn = websocket.create_connection(
        WS, header=["Authorization: Bearer " + token], timeout=8,
        http_proxy_host=proxy.hostname, http_proxy_port=proxy.port,
        http_proxy_auth=(unquote(proxy.username), unquote(proxy.password)),
        http_no_proxy=["never-match.invalid"], proxy_type="http",
        sslopt={"cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True})
    emit("WEBSOCKET_HANDSHAKE", "PASS")
    try:
        conn.send(json.dumps([{"type": "personal:order", "codes": accounts},
                              {"type": "trade:us", "codes": ["AAPL"]}]))
        raw = conn.recv()
        if not isinstance(raw, str) or len(raw) > MAX_BYTES:
            raise Blocked("ACK_INVALID")
        order_status, market_status = subscription_status(json.loads(raw), accounts)
        emit("WEBSOCKET_ORDER_SUBSCRIPTION", order_status)
        emit("WEBSOCKET_MARKET_SUBSCRIPTION", market_status)
        # This confirms subscription acceptance, never a real fill or market tick.
        return order_status == "PASS" and market_status == "PASS"
    finally:
        conn.close(timeout=1)

def run():
    stage = "CONFIG"
    try:
        proxy_url = os.environ["PROXY_URL"]
        proxy = proxy_config(proxy_url)
        client_id = os.environ["TOSS_CLIENT_ID"]
        secret = os.environ["TOSS_CLIENT_SECRET"]
        if not client_id or not secret:
            raise Blocked("MISSING_CREDENTIALS")
        emit(stage, "PASS")
        with requests.Session() as session:
            session.trust_env = False
            session.proxies = {"https": proxy_url}
            stage = "EGRESS"
            if request(session, "GET", "EGRESS").strip() != IP:
                raise Blocked("IP_MISMATCH")
            emit(stage, "PASS")
            stage = "OAUTH"
            auth = request(session, "POST", "/oauth2/token", data={
                "grant_type": "client_credentials", "client_id": client_id, "client_secret": secret})
            token = auth["access_token"]
            if not isinstance(token, str) or not token or "\r" in token or "\n" in token:
                raise Blocked("TOKEN_SCHEMA")
            emit(stage, "PASS")
            stage = "ACCOUNTS"
            accounts = get(session, token, "/api/v1/accounts")
            if not isinstance(accounts, list) or not 1 <= len(accounts) <= 10:
                raise Blocked("ACCOUNT_LIST_UNSUPPORTED")
            seqs = [str(a["accountSeq"]) for a in accounts]
            if len(set(seqs)) != len(seqs) or not all(s.isascii() and s.isdigit() for s in seqs):
                raise Blocked("ACCOUNT_SCHEMA")
            emit(stage, "PASS")
            stage = "HOLDINGS"
            holdings = [get(session, token, "/api/v1/holdings", a) for a in seqs]
            if not all(holdings_ok(h) for h in holdings):
                raise Blocked("SCHEMA_UNVERIFIED")
            complete = all(page_complete(h) for h in holdings)
            emit(stage, "PASS" if complete else "PARTIAL_PAGE")
            stage = "BUYING_POWER"
            for a in seqs:
                for currency in ("KRW", "USD"):
                    value = get(session, token, "/api/v1/buying-power", a, {"currency": currency})
                    if not finite(value["cashBuyingPower"]):
                        raise Blocked("SCHEMA_UNVERIFIED")
            emit(stage, "PASS")
            stage = "ORDERS_READ"
            orders = [get(session, token, "/api/v1/orders", a, {"status": "OPEN"}) for a in seqs]
            if not all(isinstance(v, dict) and isinstance(v.get("orders"), list) for v in orders):
                raise Blocked("SCHEMA_UNVERIFIED")
            emit(stage, "PASS" if all(page_complete(v) for v in orders) else "PARTIAL_PAGE")
            stage = "SELLABLE_READ"
            value = get(session, token, "/api/v1/sellable-quantity", seqs[0], {"symbol": "AAPL"})
            if not finite(value["sellableQuantity"]):
                raise Blocked("SCHEMA_UNVERIFIED")
            emit(stage, "PASS")
            stage = "FX"
            value = get(session, token, "/api/v1/exchange-rate", params={"baseCurrency":"USD","quoteCurrency":"KRW"})
            if not finite(value["rate"]) or Decimal(str(value["rate"])) <= 0:
                raise Blocked("SCHEMA_UNVERIFIED")
            emit(stage, "PASS")
            stage = "WEBSOCKET"
            ws_ok = ws_check(proxy, token, seqs)
            emit("SUMMARY", "READS_AND_SUBSCRIPTIONS_PASS" if complete and ws_ok else "PARTIAL")
            return 0 if complete and ws_ok else 2
    except Blocked as e:
        emit(stage, str(e))  # only fixed internal reason codes
    except requests.exceptions.ProxyError:
        emit(stage, "PROXY_ERROR")
    except requests.exceptions.Timeout:
        emit(stage, "TIMEOUT")
    except websocket.WebSocketBadStatusException as e:
        emit(stage, "WS_HTTP_" + str(e.status_code))
    except Exception as e:
        emit(stage, "FAILED_" + type(e).__name__)
    emit("SUMMARY", "BLOCKED")
    return 1

if __name__ == "__main__":
    sys.exit(run())

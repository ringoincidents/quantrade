"""Deliver one read-only account report to the configured private Telegram chat."""
import os
import sys
from datetime import datetime

import requests

from real_portfolio_sync import KST, get_access_token
from toss_account_report import collect, render


def send_report():
    print("Checking delivery configuration", flush=True)
    recipient = int(os.environ["TELEGRAM_CHAT_ID"])
    if recipient <= 0:
        raise ValueError("Private chat required")
    base = "https://api.telegram.org/bot" + os.environ["TELEGRAM_TOKEN"]
    print("Verifying private Telegram recipient", flush=True)
    response = requests.post(base + "/getChat", json={"chat_id": recipient}, timeout=15)
    response.raise_for_status()
    chat = response.json()["result"]
    if chat["type"] != "private" or chat["id"] != recipient:
        raise ValueError("Private recipient mismatch")

    print("Requesting Toss access", flush=True)
    token = get_access_token()
    print("Reading Toss holdings", flush=True)
    fx, accounts = collect(token)
    print("Formatting account report", flush=True)
    report = render(fx, accounts, datetime.now(KST))
    print("Delivering private report", flush=True)
    response = requests.post(
        base + "/sendDocument",
        data={"chat_id": recipient, "protect_content": "true"},
        files={"document": ("QuanTrade-report.txt", report.encode("utf-8"), "text/plain")},
        timeout=30,
    )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError("Delivery failed")


if __name__ == "__main__":
    try:
        send_report()
    except Exception as error:
        print(type(error).__name__, file=sys.stderr)
        if isinstance(error, requests.HTTPError) and error.response is not None:
            print(f"HTTP {error.response.status_code}", file=sys.stderr)
        raise SystemExit("비공개 계좌 보고서 전달 실패") from None

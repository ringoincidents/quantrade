"""Deliver one read-only account report to the configured private Telegram chat."""
import os
from datetime import datetime

import requests

from real_portfolio_sync import KST, get_access_token
from toss_account_report import collect, render


def send_report():
    recipient = int(os.environ["TELEGRAM_CHAT_ID"])
    if recipient <= 0:
        raise ValueError("Private chat required")
    base = "https://api.telegram.org/bot" + os.environ["TELEGRAM_TOKEN"]
    response = requests.post(base + "/getChat", json={"chat_id": recipient}, timeout=15)
    response.raise_for_status()
    chat = response.json()["result"]
    if chat["type"] != "private" or chat["id"] != recipient:
        raise ValueError("Private recipient mismatch")

    fx, accounts = collect(get_access_token())
    report = render(fx, accounts, datetime.now(KST))
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
    except Exception:
        raise SystemExit("비공개 계좌 보고서 전달 실패") from None

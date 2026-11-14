"""Read-only account report. Run locally with the existing Toss proxy and credentials.

Private account data goes only to the invoking terminal. Do not run in public CI.
"""
from datetime import datetime
from decimal import Decimal

from real_portfolio_sync import KST, TossApiError, _get_result, get_access_token


def number(value):
    if isinstance(value, dict):
        value = value["amount"]
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("유효하지 않은 금액")
    return result


def fmt(value):
    if value is None:
        return "미확인"
    return format(value, ",f").rstrip("0").rstrip(".") if "." in format(value, "f") else format(value, ",f")


def collect(token, read=_get_result):
    accounts = read("/api/v1/accounts", token)
    if not accounts:
        raise TossApiError("조회 가능한 계좌가 없습니다.")
    try:
        fx = number(read("/api/v1/exchange-rate", token, params={
            "baseCurrency": "USD", "quoteCurrency": "KRW",
        })["rate"])
        if fx <= 0:
            fx = None
    except TossApiError:
        fx = None

    result = []
    for account in accounts:
        seq = account["accountSeq"]
        balances = {}
        for currency in ("KRW", "USD"):
            power = read("/api/v1/buying-power", token, account_seq=seq, params={"currency": currency})
            balances[currency] = number(power["cashBuyingPower"])
        holdings = read("/api/v1/holdings", token, account_seq=seq)
        if holdings.get("nextCursor") or holdings.get("hasNext"):
            raise TossApiError("추가 보유내역 페이지가 있어 보고서를 확정할 수 없습니다.")
        result.append((balances, holdings["items"]))
    return fx, result


def render(fx, accounts, checked_at):
    lines = [f"토스 계좌 운용 보고서 · 조회 완료 {checked_at:%Y-%m-%d %H:%M %Z}",
             f"계좌 {len(accounts)}개 · USD/KRW {fmt(fx)}"]
    for index, (balances, holdings) in enumerate(accounts, 1):
        lines.extend(["", f"계좌 {index} · 보유 {len(holdings)}종목",
                      f"매수가능금액  KRW {fmt(balances['KRW'])} / USD {fmt(balances['USD'])}"])
        rows = []
        for item in holdings:
            currency = item["currency"]
            value = number(item["marketValue"])
            rate = {"KRW": Decimal(1), "USD": fx}.get(currency)
            rows.append((item, currency, value * rate if rate is not None else None))
        total = sum(row[2] for row in rows) if all(row[2] is not None for row in rows) else None
        for item, currency, value in rows:
            weight = f"{100 * value / total:.2f}%" if total and value is not None else "미확인"
            pnl = item.get("profitLoss") or {}
            pnl_amount = pnl.get("amount")
            pnl_rate = pnl.get("rate")
            lines.append(f"{item['symbol']} {item['name']} · {fmt(number(item['quantity']))}주 · "
                         f"평단/현재가 {fmt(number(item['averagePurchasePrice']))}/{fmt(number(item['lastPrice']))} {currency} · "
                         f"평가액 {fmt(value)}원 · 보유증권 내 비중 {weight} · "
                         f"평가손익 {fmt(number(pnl_amount) if pnl_amount is not None else None)} {currency} · "
                         f"수익률 {fmt(number(pnl_rate) * 100 if pnl_rate is not None else None)}%")
        if rows:
            lines.append("검토할 일 · 종목별 운용 기준 연결 전. 손절·익절·리밸런싱 판정 보류.")
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        rate, observed = collect(get_access_token())
        print(render(rate, observed, datetime.now(KST)))
    except Exception as error:
        # Broker and proxy error messages can contain sensitive account metadata.
        raise SystemExit(f"계좌 보고서 조회 실패 ({type(error).__name__})") from None

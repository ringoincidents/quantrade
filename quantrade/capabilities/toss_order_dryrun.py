"""Toss-like quantity order contract and OFFLINE paper gateway.

This module is intentionally incapable of network access or real order placement.
It does NOT import Toss account sync helpers or accept API credentials. It must
never be wired into autoexec.py as an execution provider without independent
Risk, Approval, order-reconciliation and live-operational verification.

Order fields are consistent with Toss order schema as documented in the
2026-08-05 research mirror; check latest official spec before implementing any
separate production connector. Offline output is not a broker acknowledgment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import re
from typing import Literal


_SYMBOL = re.compile(r"(?:[0-9A-Z]{6}|[A-Z][A-Z0-9.\-]{0,11})\Z")
_CLIENT_ID = re.compile(r"[a-zA-Z0-9_-]{1,36}\Z")
Side = Literal["BUY", "SELL"]
OrderType = Literal["LIMIT", "MARKET"]


class DryRunRejected(ValueError):
    """A fake order is rejected; it is NOT a broker response."""


def dec(value: Decimal | str | int, *, positive: bool = False) -> Decimal:
    """Strict decimal: floats and booleans cannot silently corrupt money."""
    if isinstance(value, (bool, float)) or not isinstance(value, (Decimal, str, int)):
        raise DryRunRejected("decimal value must be Decimal, str, or int")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise DryRunRejected("invalid decimal") from None
    if not result.is_finite() or result < 0 or (positive and result <= 0):
        raise DryRunRejected("decimal must be finite and valid")
    return result


def decimal_string(d: Decimal) -> str:
    return format(d, "f")


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    client_order_id: str
    price: Decimal | None = None
    time_in_force: str = "DAY"

    def payload(self) -> dict[str, object]:
        if not _SYMBOL.fullmatch(self.symbol):
            raise DryRunRejected("invalid stock symbol")
        if self.side not in ("BUY", "SELL"):
            raise DryRunRejected("invalid side")
        if self.order_type not in ("LIMIT", "MARKET"):
            raise DryRunRejected("invalid order type")
        if not _CLIENT_ID.fullmatch(self.client_order_id):
            raise DryRunRejected("invalid clientOrderId")
        if self.time_in_force != "DAY":
            raise DryRunRejected("DAY only in conservative paper contract")
        qty = dec(self.quantity, positive=True)
        # US fractions are intentionally disabled until sessions/rules are verified.
        if qty != qty.to_integral_value():
            raise DryRunRejected("whole shares only")
        payload: dict[str, object] = {
            "symbol": self.symbol,
            "side": self.side,
            "orderType": self.order_type,
            "quantity": decimal_string(qty),
            "clientOrderId": self.client_order_id,
            "timeInForce": "DAY",
        }
        if self.order_type == "LIMIT":
            if self.price is None:
                raise DryRunRejected("LIMIT requires price")
            payload["price"] = decimal_string(dec(self.price, positive=True))
        elif self.price is not None:
            raise DryRunRejected("MARKET must not specify price")
        # Never auto-confirm high-value orders.
        return payload


@dataclass(frozen=True)
class PaperContext:
    now: datetime
    quote_at: datetime
    market_open: bool
    reference_price: Decimal
    buying_power: Decimal
    sellable_quantity: Decimal
    max_notional: Decimal
    stopped: bool = True
    simulated_approval: bool = False


def check_context(intent: OrderIntent, ctx: PaperContext, *, max_quote_age_seconds: int = 20) -> Decimal:
    """Fail-closed risk check using synthetic balances, not client account state."""
    p = intent.payload()
    if ctx.stopped:
        raise DryRunRejected("kill switch is on")
    if not ctx.simulated_approval:
        raise DryRunRejected("no simulated approval")
    if not ctx.market_open:
        raise DryRunRejected("market closed")
    if ctx.now.tzinfo is None or ctx.quote_at.tzinfo is None:
        raise DryRunRejected("timezone-aware timestamps required")
    age = ctx.now - ctx.quote_at
    if not (timedelta(0) <= age <= timedelta(seconds=max_quote_age_seconds)):
        raise DryRunRejected("future or stale market data")
    reference = dec(ctx.reference_price, positive=True)
    # Conservative: reject malformed balance fields regardless of trade side.
    cash = dec(ctx.buying_power)
    held = dec(ctx.sellable_quantity)
    cap = dec(ctx.max_notional, positive=True)
    quoted = dec(intent.price, positive=True) if intent.order_type == "LIMIT" else reference
    notional = dec(intent.quantity, positive=True) * quoted
    if notional > cap:
        raise DryRunRejected("risk notional cap exceeded")
    if intent.side == "BUY" and notional > cash:
        raise DryRunRejected("insufficient synthetic buying power")
    if intent.side == "SELL" and dec(intent.quantity) > held:
        raise DryRunRejected("insufficient synthetic sellable quantity")
    return notional


@dataclass
class PaperOrderState:
    client_order_id: str
    payload: dict[str, object]
    paper_order_id: str
    status: str = "PENDING"
    filled_quantity: Decimal = Decimal(0)
    filled_value: Decimal = Decimal(0)
    fees: Decimal = Decimal(0)
    events: list[str] = field(default_factory=lambda: ["PENDING"])

    def snapshot(self) -> dict[str, str | list[str]]:
        return {
            "paperOrderId": self.paper_order_id,
            "clientOrderId": self.client_order_id,
            "status": self.status,
            "filledQuantity": decimal_string(self.filled_quantity),
            "averageFilledPrice": decimal_string(self.filled_value / self.filled_quantity) if self.filled_quantity else "0",
            "fees": decimal_string(self.fees),
            "events": list(self.events),
            "mode": "OFFLINE_PAPER_ONLY",
        }


class OfflineTossPaperGateway:
    """Memory-only paper executor; has no network or POST capability."""

    def __init__(self) -> None:
        self.orders: dict[str, PaperOrderState] = {}

    def preview(self, intent: OrderIntent, ctx: PaperContext) -> dict[str, object]:
        notional = check_context(intent, ctx)
        return {
            "mode": "OFFLINE_PAPER_ONLY",
            "wouldSendPath": "POST /api/v1/orders",  # descriptive, NOT an HTTP call
            "payload": intent.payload(),
            "referenceNotional": decimal_string(notional),
        }

    def submit(self, intent: OrderIntent, ctx: PaperContext) -> PaperOrderState:
        payload = intent.payload()
        old = self.orders.get(intent.client_order_id)
        if old is not None:
            if old.payload != payload:
                raise DryRunRejected("idempotency key conflicts with earlier paper order")
            return old  # NO second order, even if context changes
        self.preview(intent, ctx)
        new = PaperOrderState(
            client_order_id=intent.client_order_id,
            payload=payload,
            paper_order_id=f"paper-{len(self.orders) + 1:04d}",
        )
        self.orders[intent.client_order_id] = new
        return new

    def fill(self, client_order_id: str, *, quantity: Decimal | str | int, price: Decimal | str | int, fee: Decimal | str | int = "0") -> PaperOrderState:
        state = self.orders[client_order_id]
        if state.status not in ("PENDING", "PARTIAL_FILLED"):
            raise DryRunRejected("not an open paper order")
        qty = dec(quantity, positive=True)
        px = dec(price, positive=True)
        fees = dec(fee)
        if qty > dec(state.payload["quantity"]) - state.filled_quantity:
            raise DryRunRejected("overfill attempted")
        state.filled_quantity += qty
        state.filled_value += qty * px
        state.fees += fees
        state.status = "FILLED" if state.filled_quantity == dec(state.payload["quantity"]) else "PARTIAL_FILLED"
        state.events.append(state.status)
        return state

    def cancel(self, client_order_id: str) -> PaperOrderState:
        state = self.orders[client_order_id]
        if state.status not in ("PENDING", "PARTIAL_FILLED"):
            raise DryRunRejected("cannot cancel terminal order")
        state.status = "CANCELED"
        state.events.append("CANCELED")
        return state

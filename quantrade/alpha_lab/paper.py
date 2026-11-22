"""Offline-only simulated stock fills for QuanTrade's Alpha Lab.

No credentials, network I/O, broker adapter, live-trading interface, or order
submission code exists here. This is a conservative single-quote approximation,
NOT evidence of real execution quality or profitability.

Amounts and quotes are USDC/USD-denominated for this experiment. Convert KRW
starting capital separately using a documented contemporaneous FX rate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


class PaperRejected(ValueError):
    """The paper engine refuses an invalid or unfillable simulated order."""


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


def _positive(v: Decimal, name: str) -> None:
    if not v.is_finite() or v <= 0:
        raise PaperRejected(f"{name} must be a finite positive Decimal")


def _nonnegative(v: Decimal, name: str) -> None:
    if not v.is_finite() or v < 0:
        raise PaperRejected(f"{name} must be a finite nonnegative Decimal")


@dataclass(frozen=True)
class EquityQuote:
    symbol: str
    bid: Decimal
    ask: Decimal
    observed_at: datetime
    market_open: bool

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol != self.symbol.upper():
            raise PaperRejected("symbol must be nonempty uppercase ticker")
        _positive(self.bid, "bid")
        _positive(self.ask, "ask")
        if self.bid > self.ask:
            raise PaperRejected("crossed quote is not supported")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise PaperRejected("quote must have timezone-aware timestamp")


@dataclass(frozen=True)
class PaperRequest:
    client_order_id: str
    side: Side
    quantity: Decimal
    quote: EquityQuote
    submitted_at: datetime

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise PaperRejected("client_order_id is required")
        if not isinstance(self.side, Side):
            raise PaperRejected("side must be Side.BUY or Side.SELL")
        _positive(self.quantity, "quantity")
        if self.submitted_at.tzinfo is None or self.submitted_at.utcoffset() is None:
            raise PaperRejected("order must have timezone-aware timestamp")


@dataclass(frozen=True)
class PaperFill:
    client_order_id: str
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    gross_notional: Decimal
    platform_fee: Decimal
    cash_after: Decimal
    position_after: Decimal
    submitted_at: datetime


@dataclass(frozen=True)
class PaperRules:
    """Experimental fee floor restricted to <= 350 USD orders.

    Binance Stocks' currently published <=350 USD minimum platform fee
    is 0.35 USD per order. Above this tier, consult an up-to-date fee schedule
    instead of extrapolating from this model.
    """

    min_order_notional: Decimal = Decimal("5")
    max_model_notional: Decimal = Decimal("350")
    minimum_platform_fee: Decimal = Decimal("0.35")
    slippage_bps: Decimal = Decimal("0")
    max_quote_age: timedelta = timedelta(seconds=5)

    def __post_init__(self) -> None:
        _positive(self.min_order_notional, "min_order_notional")
        _positive(self.max_model_notional, "max_model_notional")
        _nonnegative(self.minimum_platform_fee, "minimum_platform_fee")
        _nonnegative(self.slippage_bps, "slippage_bps")
        if self.min_order_notional > self.max_model_notional:
            raise PaperRejected("minimum notional exceeds supported tier")
        if self.max_quote_age <= timedelta(0):
            raise PaperRejected("max_quote_age must be positive")


@dataclass
class PaperAccount:
    """In-memory single-quote paper execution; intentionally no persistence."""

    initial_cash: Decimal
    rules: PaperRules = field(default_factory=PaperRules)
    cash: Decimal = field(init=False)
    positions: dict[str, Decimal] = field(default_factory=dict, init=False)
    fills: list[PaperFill] = field(default_factory=list, init=False)
    _seen: dict[str, tuple[PaperRequest, PaperFill]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        _nonnegative(self.initial_cash, "initial_cash")
        self.cash = self.initial_cash

    def submit(self, order: PaperRequest) -> PaperFill:
        """Execute an immediate *simulated* market fill at bid/ask + slippage.

        Reject stale/closed quotes, unsupported fee tiers and insufficient cash.
        No margin, shorting, commissions exemptions, partial fills, or live I/O.
        Retries are idempotent only when the full request is identical.
        """
        prior = self._seen.get(order.client_order_id)
        if prior is not None:
            if order != prior[0]:
                raise PaperRejected("client_order_id reused with a different request")
            return prior[1]

        quote = order.quote
        if not quote.market_open:
            raise PaperRejected("market closed: paper market order not filled")
        age = order.submitted_at - quote.observed_at
        if age < timedelta(0) or age > self.rules.max_quote_age:
            raise PaperRejected("quote is stale or dated in the future")
        factor = self.rules.slippage_bps / Decimal("10000")
        price = quote.ask * (Decimal("1") + factor) if order.side is Side.BUY else quote.bid * (Decimal("1") - factor)
        _positive(price, "execution price")
        gross = order.quantity * price
        if gross < self.rules.min_order_notional:
            raise PaperRejected("below symbol's configured minimum order notional")
        if gross > self.rules.max_model_notional:
            raise PaperRejected("over unsupported fee tier: update fee model first")

        fee = self.rules.minimum_platform_fee
        current = self.positions.get(quote.symbol, Decimal("0"))
        if order.side is Side.BUY:
            required = gross + fee
            if required > self.cash:
                raise PaperRejected("insufficient paper cash including fees")
            next_cash, next_position = self.cash - required, current + order.quantity
        else:
            if order.quantity > current:
                raise PaperRejected("short selling is disabled")
            next_cash, next_position = self.cash + gross - fee, current - order.quantity

        fill = PaperFill(
            client_order_id=order.client_order_id, symbol=quote.symbol,
            side=order.side, quantity=order.quantity, price=price,
            gross_notional=gross, platform_fee=fee,
            cash_after=next_cash, position_after=next_position,
            submitted_at=order.submitted_at,
        )
        self.cash = next_cash
        self.positions[quote.symbol] = next_position
        self.fills.append(fill)
        self._seen[order.client_order_id] = (order, fill)
        return fill

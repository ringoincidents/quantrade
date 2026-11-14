"""Manual live probe for the Open DART fundamental provider.

The probe is intentionally read-only. It requires OPEN_DART_API_KEY and writes
no repository state unless the caller redirects stdout.

Example:
  python -m scripts.run_dart_fundamental_probe \
    --stock-code 005930 \
    --as-of 2026-10-05T23:59:59+09:00 \
    --period-from 2025-01-01 \
    --period-to 2025-12-31
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from quantrade.capabilities.dart_fundamental_provider import (
    DartFundamentalObservationProvider,
)
from quantrade.capabilities.fundamental_evidence import FundamentalQuery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--period-from", required=True)
    parser.add_argument("--period-to", required=True)
    parser.add_argument(
        "--metric-key",
        action="append",
        default=[],
        help="Repeat to filter normalized metric keys.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    provider = DartFundamentalObservationProvider()
    result = provider.query(
        FundamentalQuery(
            asset_id=f"KRX:{args.stock_code}",
            as_of=args.as_of,
            metric_keys=tuple(args.metric_key),
            fiscal_period_end_from=args.period_from,
            fiscal_period_end_to=args.period_to,
        )
    )
    output = asdict(result)
    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

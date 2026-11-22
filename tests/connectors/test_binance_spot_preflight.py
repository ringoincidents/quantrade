"""Safe credential-preflight regression tests without contacting Binance."""
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from quantrade.connectors import binance_spot_preflight


class ReadOnlyPreflightTests(unittest.TestCase):
    def test_no_credentials_never_attempts_private(self):
        with patch.dict(os.environ, {"QUANTRADE_BINANCE_API_KEY": "", "QUANTRADE_BINANCE_API_SECRET": ""}):
            with patch.object(binance_spot_preflight.PublicSpotData, "server_time", return_value=1):
                with patch.object(binance_spot_preflight.AccountReadOnly, "from_environment") as private:
                    output = io.StringIO()
                    with redirect_stdout(output):
                        rc = binance_spot_preflight.main()
                    self.assertEqual(rc, 1)
                    self.assertEqual(json.loads(output.getvalue())["private_account"], "NOT_CONFIGURED")
                    private.assert_not_called()

    def test_success_no_secret_or_balance_in_log(self):
        with patch.dict(os.environ, {"QUANTRADE_BINANCE_API_KEY": "API_SENSITIVE", "QUANTRADE_BINANCE_API_SECRET": "SECRET_SENSITIVE"}):
            with patch.object(binance_spot_preflight.PublicSpotData, "server_time", return_value=1):
                with patch.object(binance_spot_preflight.AccountReadOnly, "verified_permissions", return_value={"read_only_verified": True}):
                    with patch.object(binance_spot_preflight.AccountReadOnly, "balances", return_value=[{"asset":"USDT","free":"10.0","locked":"0"}]):
                        output = io.StringIO()
                        with redirect_stdout(output):
                            rc = binance_spot_preflight.main()
                        self.assertEqual(rc, 0)
                        result = json.loads(output.getvalue())
                        self.assertEqual(result["private_account"], "VERIFIED_READ_ONLY")
                        self.assertFalse(result["orders_enabled"])
                        self.assertNotIn("API_SENSITIVE", output.getvalue())
                        self.assertNotIn("SECRET_SENSITIVE", output.getvalue())
                        self.assertNotIn("10.0", output.getvalue())


if __name__ == "__main__":
    unittest.main()

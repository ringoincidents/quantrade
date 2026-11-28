import unittest
import json
import ssl
from unittest.mock import MagicMock
from datetime import datetime,timezone
from decimal import Decimal
from broker_reader import (TLSProxyTransport,BrokerReader,proxy_parts,Blocked,HTTPStatus,
                           EXPECTED_IP,MAX_BYTES,TransportFailure,strict_json)
NOW=datetime(2026,11,28,tzinfo=timezone.utc)
PROXY="https://fixture:synthetic@proxy.example.invalid:443"
class Fake:
    def __init__(self):
        self.calls=[]
        self.ip=EXPECTED_IP
        self.fail=None
    def request(self,method,path,**kw):
        self.calls.append((method,path))
        if self.fail==path:
            raise HTTPStatus(401)
        if path=="EGRESS":return self.ip
        if path=="/oauth2/token":return {"access_token":"synthetic.token","token_type":"Bearer","expires_in":86400}
        if path=="/api/v1/accounts":return {"result":[{"accountSeq":"123456789"}]}
        if path=="/api/v1/holdings":return {"result":{"items":[{"symbol":"FIXTURE","currency":"USD","quantity":Decimal("1.25"),"lastPrice":Decimal("100.12"),"marketValue":{"amount":Decimal("125.15")}}],"hasNext":False}}
        if path=="/api/v1/buying-power":return {"result":{"cashBuyingPower":"100"}}
        if path=="/api/v1/exchange-rate":return {"result":{"rate":"1400"}}
        raise AssertionError("unexpected route")

class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.t=Fake();self.clock=[1000]
        self.reader=BrokerReader(self.t,"fixture-id","fixture-secret",clock=lambda:self.clock[0],wall=lambda:NOW)
    def test_egress_before_oauth_and_token_reuse(self):
        r=self.reader.refresh()
        self.reader.refresh()
        self.assertEqual(self.t.calls[:2],[("GET","EGRESS"),("POST","/oauth2/token")])
        self.assertEqual(self.t.calls.count(("POST","/oauth2/token")),1)
        self.assertEqual(r["securities_value_krw"],"175210.00")
        self.assertIsNone(r["total_nav"])
        self.assertNotIn("123456789",json.dumps(r))
        self.assertFalse(r["order_authorized"])
    def test_egress_mismatch_no_token(self):
        self.t.ip="192.0.2.1"
        with self.assertRaisesRegex(Blocked,"EGRESS_MISMATCH"):
            self.reader.refresh()
        self.assertEqual(self.t.calls,[("GET","EGRESS")])
    def test_401_no_automatic_reissue(self):
        self.t.fail="/api/v1/holdings"
        with self.assertRaisesRegex(Blocked,"BROKER_HTTP_401"):
            self.reader.refresh()
        self.t.fail=None
        with self.assertRaisesRegex(Blocked,"TOKEN_ISSUE_COOLDOWN"):
            self.reader.refresh()
        self.assertEqual(self.t.calls.count(("POST","/oauth2/token")),1)
        self.clock[0]+=61
        self.reader.refresh()
        self.assertEqual(self.t.calls.count(("POST","/oauth2/token")),2)
    def test_fx_401_not_silently_partial(self):
        self.t.fail="/api/v1/exchange-rate"
        with self.assertRaisesRegex(Blocked,"BROKER_HTTP_401"):
            self.reader.refresh()
    def test_single_refresh_lane(self):
        self.reader.lock.acquire()
        try:
            with self.assertRaisesRegex(Blocked,"REFRESH_BUSY"):self.reader.refresh()
            self.assertEqual(self.t.calls,[])
        finally:self.reader.lock.release()
    def test_token_issue_failure_cooldown(self):
        self.t.fail="/oauth2/token"
        with self.assertRaises(HTTPStatus):self.reader.refresh()
        with self.assertRaisesRegex(Blocked,"TOKEN_ISSUE_COOLDOWN"):self.reader.refresh()
        self.assertEqual(self.t.calls.count(("POST","/oauth2/token")),1)

class TransportTests(unittest.TestCase):
    def test_tls_required_before_network(self):
        factory=MagicMock()
        with self.assertRaisesRegex(Blocked,"TLS_PROXY_REQUIRED"):
            TLSProxyTransport("http://fixture:secret@proxy.example.invalid:3128",factory)
        factory.assert_not_called()
        self.assertEqual(proxy_parts(PROXY)[0],"https://proxy.example.invalid:443")
    def test_tls_context_and_allowlist(self):
        factory=MagicMock()
        t=TLSProxyTransport(PROXY,factory)
        k=factory.call_args.kwargs
        for ctx in (k["ssl_context"],k["proxy_ssl_context"]):
            self.assertTrue(ctx.check_hostname)
            self.assertEqual(ctx.verify_mode,ssl.CERT_REQUIRED)
        self.assertFalse(k["use_forwarding_for_https"])
        for method,path in [("POST","/api/v1/orders"),("DELETE","/api/v1/orders"),("GET","https://evil.invalid")]:
            with self.assertRaisesRegex(Blocked,"METHOD_NOT_ALLOWED"):t.request(method,path)
        factory.return_value.request.assert_not_called()
    def test_no_redirect_retry_and_bounded_decimal(self):
        factory=MagicMock(); t=TLSProxyTransport(PROXY,factory)
        res=factory.return_value.request.return_value
        res.status=200;res.headers={};res.read.return_value=b'{"result":{"price":100.12}}'
        result=t.request("GET","/api/v1/holdings")
        self.assertEqual(result["result"]["price"],Decimal("100.12"))
        k=factory.return_value.request.call_args.kwargs
        self.assertFalse(k["redirect"]);self.assertFalse(k["retries"])
        res.read.assert_called_once_with(MAX_BYTES+1,decode_content=False)
        res.status=302
        with self.assertRaisesRegex(Blocked,"BROKER_HTTP_302"):t.request("GET","/api/v1/holdings")
        res.status=200;res.read.return_value=b"x"*(MAX_BYTES+1)
        with self.assertRaisesRegex(Blocked,"RESPONSE_TOO_LARGE"):t.request("GET","/api/v1/holdings")
    def test_ambiguous_json(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):strict_json(raw)

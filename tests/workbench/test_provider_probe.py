import unittest
import io
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock
from unittest.mock import patch
from quantrade.workbench import provider_probe as p

class ProbeTests(unittest.TestCase):
    def test_krx_match(self):
        row={"BAS_DD":p.DATE.replace("-",""),"ISU_CD":"005930","TDD_CLSPRC":"100000"}
        with patch.object(p,"request_json",return_value=("HTTP_200",{"OutBlock_1":[row]})):
            self.assertEqual(p.krx("stk_bydd_trd","fixture","005930"),"PASS_SCHEMA")
            self.assertEqual(p.krx("stk_bydd_trd","fixture","000000"),"HTTP_200_SCHEMA_OR_SYMBOL_MISMATCH")
    def test_massive_match(self):
        with patch.object(p,"request_json",return_value=("HTTP_200",{"status":"OK","symbol":"AAPL","from":p.DATE,"close":"100.25"})):
            self.assertEqual(p.massive("AAPL","fixture"),"PASS_SCHEMA")
            self.assertEqual(p.massive("IBM","fixture"),"HTTP_200_SCHEMA_OR_SYMBOL_MISMATCH")
    def test_deny(self):
        with patch.object(p,"request_json",return_value=("HTTP_403",None)):
            self.assertEqual(p.krx("stk_bydd_trd","fixture"),"HTTP_403")
            self.assertEqual(p.massive("AAPL","fixture"),"HTTP_403")
    def test_aggregate_exit(self):
        with patch.object(p,"krx",return_value="HTTP_401"), patch.object(p,"massive",return_value="PASS_SCHEMA"), patch("builtins.print") as out:
            self.assertEqual(p.main(),1)
            self.assertTrue(any('"passed": 2' in str(c) for c in out.call_args_list))
        with patch.object(p,"krx",return_value="PASS_SCHEMA"), patch.object(p,"massive",return_value="PASS_SCHEMA"), patch("builtins.print"):
            self.assertEqual(p.main(),0)
    def test_missing(self):
        self.assertEqual(p.request_json("https://example.invalid","AUTH_KEY",""),("KEY_MISSING",None))
    def test_transport_headers_timeout_and_size(self):
        response=MagicMock()
        response.status=200
        response.__enter__.return_value=response
        response.read.return_value=b'{"close": 12.5}'
        with patch.object(p,"build_opener") as make:
            opener=make.return_value
            opener.open.return_value=response
            status,data=p.request_json("https://example.invalid","AUTH_KEY","fixture")
            self.assertEqual(status,"HTTP_200")
            self.assertEqual(str(data["close"]),"12.5")
            req=opener.open.call_args.args[0]
            self.assertEqual(req.get_header("Auth_key"),"fixture")
            self.assertEqual(opener.open.call_args.kwargs["timeout"],15)
            self.assertIsInstance(make.call_args.args[0],p.NoRedirect)
            response.read.assert_called_once_with(8_000_001)
            response.read.return_value=b"x"*8_000_001
            self.assertEqual(p.request_json("https://example.invalid","AUTH_KEY","fixture"),("RESPONSE_TOO_LARGE",None))
            response.status=206
            self.assertEqual(p.request_json("https://example.invalid","AUTH_KEY","fixture"),("HTTP_206",None))

    def test_transport_errors_and_parse(self):
        for error,expected in [(TimeoutError("fixture-secret"),"TRANSPORT_OR_PARSE_ERROR"),
                               (URLError("fixture-secret"),"TRANSPORT_OR_PARSE_ERROR"),
                               (HTTPError("https://example.invalid",429,"fixture-secret",{},io.BytesIO(b"private")),"HTTP_429")]:
            with patch.object(p,"build_opener") as make:
                make.return_value.open.side_effect=error
                self.assertEqual(p.request_json("https://example.invalid","AUTH_KEY","fixture"),(expected,None))
        response=MagicMock()
        response.status=200
        response.__enter__.return_value=response
        with patch.object(p,"build_opener") as make:
            make.return_value.open.return_value=response
            for raw,expected in [(b"not json","TRANSPORT_OR_PARSE_ERROR"),(b"[]","INVALID_SCHEMA"),(b"\xff","TRANSPORT_OR_PARSE_ERROR")]:
                response.read.return_value=raw
                self.assertEqual(p.request_json("https://example.invalid","AUTH_KEY","fixture"),(expected,None))

    def test_real_loopback_redirect_never_followed(self):
        hits=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                hits.append(self.path)
                if self.path=="/redirect":
                    self.send_response(302)
                    self.send_header("Location","/destination")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{}')
        with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                url="http://127.0.0.1:"+str(server.server_port)
                with patch.dict("os.environ",{"no_proxy":"127.0.0.1","NO_PROXY":"127.0.0.1"}):
                    self.assertEqual(p.request_json(url+"/redirect","AUTH_KEY","fixture"),("HTTP_302",None))
                    self.assertEqual(hits,["/redirect"])
                    self.assertEqual(p.request_json(url+"/ok","AUTH_KEY","fixture"),("HTTP_200",{}))
            finally:
                server.shutdown()
                thread.join(timeout=2)

    def test_invalid_prices(self):
        for value in [None,"NaN","Infinity","-1","0"]:
            self.assertFalse(p.positive(value))

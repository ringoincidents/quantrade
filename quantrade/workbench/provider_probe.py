"""One-shot entitlement probe. No price values, keys, or raw responses in logs."""
import json
import os
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

DATE = "2026-11-25"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def positive(value):
    try:
        d = Decimal(str(value))
        return d.is_finite() and d > 0
    except (InvalidOperation, ValueError):
        return False

def request_json(url, header, key):
    if not key:
        return "KEY_MISSING", None
    try:
        req = Request(url, headers={header: key, "Accept": "application/json"})
        with build_opener(NoRedirect()).open(req, timeout=15) as res:
            raw = res.read(8_000_001)
            if len(raw)>8_000_000:
                return "RESPONSE_TOO_LARGE", None
            obj=json.loads(raw,parse_float=Decimal)
            if not isinstance(obj,dict):
                return "INVALID_SCHEMA",None
            return "HTTP_200",obj
    except HTTPError as e:
        return "HTTP_"+str(e.code),None
    except (URLError,TimeoutError,OSError,ValueError):
        return "TRANSPORT_OR_PARSE_ERROR",None

def krx(endpoint, key, symbol=None):
    status, data = request_json("https://data-dbg.krx.co.kr/svc/apis/sto/"+endpoint+"?basDd="+DATE.replace("-",""),"AUTH_KEY",key)
    if data is None:
        return status
    rows=data.get("OutBlock_1")
    if not isinstance(rows,list):
        return "HTTP_200_NO_EXPECTED_SCHEMA"
    if not rows:
        return "HTTP_200_EMPTY"
    valid=[r for r in rows if isinstance(r,dict) and r.get("BAS_DD")==DATE.replace("-","") and isinstance(r.get("ISU_CD"),str) and positive(r.get("TDD_CLSPRC"))]
    if symbol is not None:
        valid=[r for r in valid if r["ISU_CD"]==symbol]
    return "PASS_SCHEMA" if valid and (symbol is None or len(valid)==1) else "HTTP_200_SCHEMA_OR_SYMBOL_MISMATCH"

def massive(symbol,key):
    status,data=request_json("https://api.massive.com/v1/open-close/"+symbol+"/"+DATE+"?adjusted=false","Authorization","Bearer "+key if key else "")
    if data is None:
        return status
    if data.get("status")!="OK":
        return "HTTP_200_PROVIDER_ERROR"
    return "PASS_SCHEMA" if data.get("symbol")==symbol and data.get("from")==DATE and positive(data.get("close")) else "HTTP_200_SCHEMA_OR_SYMBOL_MISMATCH"

def main():
    # Fixed public fixture, not a live quote or portfolio. Only status codes leave this process.
    kr=os.environ.get("KRX_API_KEY","")
    us=os.environ.get("MASSIVE_API_KEY","")
    for label,fn in [
        ("KRX_KOSPI",lambda:krx("stk_bydd_trd",kr,"005930")),
        ("KRX_KOSDAQ",lambda:krx("ksq_bydd_trd",kr)),
        ("MASSIVE_AAPL",lambda:massive("AAPL",us)),
        ("MASSIVE_IBM",lambda:massive("IBM",us)),
    ]:
        try:
            status=fn()
        except Exception:
            status="UNEXPECTED_ERROR"
        print("F08_PROBE "+label+" "+status,flush=True)
    print("F08_PROBE FINISHED; no persisted prices, no orders",flush=True)
if __name__=="__main__":
    main()

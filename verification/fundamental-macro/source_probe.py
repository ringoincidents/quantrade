"""Bounded DART/FRED read-only public data probe; status/count only, no retention."""
import json
import os
import re
import unittest
from decimal import Decimal, InvalidOperation
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock

MAX_BODY=4*1024*1024
CORP="00126380"  # Samsung Electronics, official OpenDART example
YEAR="2025"
REPORT="11011"
SERIES="DGS10"
START="2026-11-23"
END="2026-11-25"

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def amount(x):
    if not isinstance(x,str) or not re.fullmatch(r"-?\d{1,3}(?:,\d{3})+|-?\d+(?:\.\d+)?",x):
        raise ValueError("invalid amount")
    n=Decimal(x.replace(",",""))
    if not n.is_finite():
        raise ValueError("invalid amount")
    return n

def dart(data):
    if data.get("status")!="000":
        code=data.get("status")
        return ("DART_STATUS_"+code if isinstance(code,str) and re.fullmatch(r"\d{3}",code) else "DART_PROVIDER_ERROR",0)
    rows=data.get("list")
    if not isinstance(rows,list) or not rows:
        return ("SCHEMA_INVALID",0)
    required={"BS","IS","CF"}
    seen=set()
    valid=0
    for r in rows:
        if not isinstance(r,dict) or r.get("corp_code")!=CORP or r.get("bsns_year")!=YEAR or r.get("reprt_code")!=REPORT or r.get("fs_div","CFS")!="CFS":
            return ("IDENTITY_MISMATCH",0)
        if r.get("currency")!="KRW" or not re.fullmatch(r"\d{14}",str(r.get("rcept_no",""))):
            return ("PROVENANCE_INVALID",0)
        if r.get("thstrm_amount") not in (None,"","-"):
            amount(r["thstrm_amount"])
            seen.add(r.get("sj_div"))
            valid+=1
    return ("PASS_SCHEMA" if required<=seen else "INCOMPLETE_STATEMENTS",valid)

def fred(data):
    rows=data.get("observations")
    if not isinstance(rows,list) or not rows:
        return ("SCHEMA_INVALID",0)
    dates=set()
    for r in rows:
        d=r["date"]
        if not START<=d<=END or date.fromisoformat(d).isoformat()!=d or d in dates:
            return ("DATE_MISMATCH",0)
        dates.add(d)
        if not r.get("realtime_start") or not r.get("realtime_end") or amount(r["value"])<=0:
            return ("VALUE_OR_VINTAGE_INVALID",0)
    return ("PASS_SCHEMA",len(dates))

def run(name,env=None,opener=None):
    env=os.environ if env is None else env
    key=env.get(name+"_API_KEY")
    if not key:
        return ("MISSING_KEY",0)
    if name=="DART":
        url="https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?"+urlencode(dict(crtfc_key=key,corp_code=CORP,bsns_year=YEAR,reprt_code=REPORT,fs_div="CFS"))
        parser=dart
    else:
        url="https://api.stlouisfed.org/fred/series/observations?"+urlencode(dict(api_key=key,series_id=SERIES,file_type="json",observation_start=START,observation_end=END))
        parser=fred
    try:
        req=Request(url,headers={"Accept":"application/json"},method="GET")
        if opener is None:
            opener=build_opener(ProxyHandler({}),NoRedirect())
        with opener.open(req,timeout=15) as r:
            if r.status!=200:
                return ("HTTP_"+str(r.status),0)
            body=r.read(MAX_BODY+1)
        if len(body)>MAX_BODY:
            return ("RESPONSE_TOO_LARGE",0)
        return parser(json.loads(body))
    except HTTPError as e:
        return ("HTTP_"+str(e.code),0)
    except (URLError,TimeoutError,OSError):
        return ("TRANSPORT_ERROR",0)
    except (ValueError,TypeError,KeyError,AttributeError,InvalidOperation):
        return ("SCHEMA_OR_PARSE_ERROR",0)
    except Exception:
        return ("UNEXPECTED_ERROR",0)

class Tests(unittest.TestCase):
    def test_dart(self):
        row=dict(corp_code=CORP,bsns_year=YEAR,reprt_code=REPORT,fs_div="CFS",currency="KRW",rcept_no="20260301000001",thstrm_amount="1,000")
        self.assertEqual(dart({"status":"000","list":[dict(row,sj_div=s) for s in ["BS","IS","CF"]]}),("PASS_SCHEMA",3))
    def test_dart_error(self):
        self.assertEqual(dart({"status":"010"}),("DART_STATUS_010",0))
    def test_fred(self):
        self.assertEqual(fred({"observations":[{"date":START,"value":"4.5","realtime_start":END,"realtime_end":END}]}),("PASS_SCHEMA",1))
    def test_fred_duplicate(self):
        row={"date":START,"value":"4.5","realtime_start":END,"realtime_end":END}
        self.assertEqual(fred({"observations":[row,row]})[0],"DATE_MISMATCH")
    def test_missing_key(self):
        o=MagicMock()
        self.assertEqual(run("DART",{},o),("MISSING_KEY",0))
        o.open.assert_not_called()
    def test_secret_not_in_status(self):
        o=MagicMock()
        o.open.side_effect=HTTPError("https://example.invalid/?key=secret",401,"secret",{},None)
        self.assertEqual(run("FRED",{"FRED_API_KEY":"secret"},o),("HTTP_401",0))
    def test_amount(self):
        self.assertEqual(amount("-1,500"),Decimal("-1500"))
        with self.assertRaises(ValueError):
            amount("1,2")

def main():
    print("FUNDAMENTAL_MACRO_PROBE fixed public fixtures no retention",flush=True)
    for name in ("DART","FRED"):
        status,count=run(name)
        print(name,status,"valid_rows",count,flush=True)
    print("FINISHED inspect each result; no ongoing collector",flush=True)

if __name__=="__main__":
    import sys
    if sys.argv[1:]==["--test"]:
        unittest.main(argv=[sys.argv[0]])
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit(2)

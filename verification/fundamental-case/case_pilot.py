"""Read-only, one-shot integration of the existing #119 DART provider.
No real data persistence, no external model, no valuation/trading authority.
"""
import json, os, unittest
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from quantrade.capabilities.dart_fundamental_provider import DartFundamentalObservationProvider, DartProviderConfig
from quantrade.capabilities.fundamental_evidence import FundamentalQuery

KEYS={
 "assets":"TOTAL_ASSETS:BS:CURRENT_PERIOD",
 "liabilities":"TOTAL_LIABILITIES:BS:CURRENT_PERIOD",
 "equity":"TOTAL_EQUITY:BS:CURRENT_PERIOD",
 "revenue":"REVENUE:IS:CURRENT_PERIOD",
 "operating_income":"OPERATING_INCOME:IS:CURRENT_PERIOD",
 "net_income":"NET_INCOME:IS:CURRENT_PERIOD",
}
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class Transport:
    def __init__(self):
        self.calls=0
        self.opener=build_opener(ProxyHandler({}),NoRedirect())
    def get_json(self,endpoint,params):
        if endpoint not in ("list.json","fnlttSinglAcntAll.json") or self.calls>=6:
            raise ValueError("REQUEST_LIMIT")
        self.calls+=1
        url="https://opendart.fss.or.kr/api/"+endpoint+"?"+urlencode(params)
        with self.opener.open(Request(url,headers={"Accept":"application/json"}),timeout=15) as res:
            if res.status!=200:raise ValueError("HTTP_STATUS")
            b=res.read(4*1024*1024+1)
        if len(b)>4*1024*1024:raise ValueError("BODY_LIMIT")
        data=json.loads(b)
        if not isinstance(data,dict):raise ValueError("INVALID_ROOT")
        return data
    def get_bytes(self,*args):
        raise ValueError("ARCHIVE_NOT_ALLOWED")

def analyze(rows):
    found={}
    for name,key in KEYS.items():
        matches=[r for r in rows if r["metric_key"]==key]
        if len(matches)!=1:
            return {"state":"BLOCKED_METRIC","metric":name,"matches":len(matches)}
        row=matches[0]
        if row["asset_id"]!="KRX:005930" or row["currency"]!="KRW" or row["fiscal_period_end"]!="2025-12-31":
            return {"state":"BLOCKED_IDENTITY"}
        found[name]=row
    receipts={r["source_document_id"] for r in found.values()}
    if len(receipts)!=1:return {"state":"BLOCKED_RECEIPT_MISMATCH"}
    receipt=next(iter(receipts))
    if not isinstance(receipt,str) or len(receipt)!=14 or not receipt.isascii() or not receipt.isdigit():
        return {"state":"BLOCKED_RECEIPT"}
    with localcontext() as ctx:
        ctx.prec=40
        a={k:Decimal(str(r["value"])) for k,r in found.items()}
        if not all(v.is_finite() for v in a.values()) or min(a["assets"],a["equity"],a["revenue"])<=0 or a["liabilities"]<0:
            return {"state":"BLOCKED_VALUE"}
        # Float conversion in existing provider means tolerance is explicitly bounded.
        gap=abs(a["assets"]-a["liabilities"]-a["equity"])
        if gap>Decimal("1000"):return {"state":"BLOCKED_ACCOUNTING_IDENTITY"}
        ratios={"operating_margin_pct":a["operating_income"]/a["revenue"]*100,
                "net_margin_pct":a["net_income"]/a["revenue"]*100,
                "liabilities_to_equity_pct":a["liabilities"]/a["equity"]*100}
        return {"state":"REPORT_READY","asset_id":"KRX:005930","period":"2025-12-31",
                "filing_ref":receipt,"publication_date_eod":found["assets"]["published_at"],
                "metrics":{k:str((v/Decimal(10**12)).quantize(Decimal("0.001"))) for k,v in a.items()},
                "metric_unit":"KRW_TRILLION","ratios":{k:str(v.quantize(Decimal("0.01"))) for k,v in ratios.items()},
                "accounting_identity_check":"PASS_WITHIN_1000_KRW","independent_review":"PENDING",
                "valuation_authority":False,"portfolio_authority":False,"trade_authority":False}

class Tests(unittest.TestCase):
    def fixture(self):
        vals=[300,100,200,150,30,15]
        return [dict(metric_key=k,value=v*10**12,asset_id="KRX:005930",currency="KRW",fiscal_period_end="2025-12-31",source_document_id="20260301000001",published_at="2026-03-01T23:59:59+09:00") for k,v in zip(KEYS.values(),vals)]
    def test_report(self):
        r=analyze(self.fixture())
        self.assertEqual(r["ratios"]["operating_margin_pct"],"20.00")
        self.assertEqual(r["ratios"]["liabilities_to_equity_pct"],"50.00")
        self.assertFalse(r["trade_authority"])
    def test_missing(self):self.assertEqual(analyze(self.fixture()[:-1])["state"],"BLOCKED_METRIC")
    def test_duplicate(self):
        r=self.fixture()
        self.assertEqual(analyze(r+[r[0]])["state"],"BLOCKED_METRIC")
    def test_balance(self):
        r=self.fixture();r[0]["value"]+=10000
        self.assertEqual(analyze(r)["state"],"BLOCKED_ACCOUNTING_IDENTITY")
    def test_receipt(self):
        r=self.fixture();r[0]["source_document_id"]="20260302000001"
        self.assertEqual(analyze(r)["state"],"BLOCKED_RECEIPT_MISMATCH")
    def test_scope(self):
        r=self.fixture();r[0]["currency"]="USD"
        self.assertEqual(analyze(r)["state"],"BLOCKED_IDENTITY")

def main():
    print("FUNDAMENTAL_CASE start fixed annual report",flush=True)
    key=os.getenv("DART_API_KEY")
    if not key:
        print("CASE_BLOCKED MISSING_KEY",flush=True);return
    transport=Transport()
    # One common clock for query and provider. Existing provider checks receipt/date.
    now=datetime.now(timezone.utc)
    try:
        p=DartFundamentalObservationProvider(api_key=key,transport=transport,
            config=DartProviderConfig(statement_scope="CFS",allow_ofs_fallback=False,max_list_pages=4,report_codes=("11011",)),
            now=lambda:now,corp_code_overrides={"005930":"00126380"})
        result=p.query(FundamentalQuery(asset_id="KRX:005930",as_of=now.isoformat(),
            metric_keys=tuple(KEYS.values()),fiscal_period_end_from="2025-12-31",fiscal_period_end_to="2025-12-31"))
        report=analyze(result.observations)
        # No raw response, URLs containing secrets, or exception text. Compact public filing facts only.
        print("CASE_REPORT "+json.dumps(report,sort_keys=True),flush=True)
    except Exception as e:
        print("CASE_BLOCKED "+type(e).__name__,flush=True)
    print("FINISHED requests "+str(transport.calls),flush=True)
if __name__=="__main__":
    import sys
    if sys.argv[1:]==["--test"]:unittest.main(argv=[sys.argv[0]])
    elif not sys.argv[1:]:main()
    else:raise SystemExit(2)

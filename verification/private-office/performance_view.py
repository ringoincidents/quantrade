"""Research-only performance accounting on explicit cash-flow boundary marks.
No securities-only NAV substitution, no live portfolio read, no approval.
"""
from decimal import Decimal,Context,localcontext
from datetime import datetime
from html import escape
from portfolio_projection import number,instant,require,text
SCHEMA="performance-boundary-v1"
def stamp(s):
    try:return instant(datetime.fromisoformat(s))
    except (ValueError,TypeError):raise ValueError("INVALID_TIMESTAMP") from None

def evaluate(marks,*,currency,scope,flow_coverage_confirmed=False):
    require(currency in ("KRW","USD") and scope=="FULL_NAV","FULL_NAV_REQUIRED")
    require(flow_coverage_confirmed is True,"FLOW_COVERAGE_REQUIRED")
    require(isinstance(marks,list) and 2<=len(marks)<=10000,"INVALID_MARKS")
    with localcontext(Context(prec=80)):
        first=last=None;prev=None;index=peak=Decimal(1);dd=Decimal(0);flows=Decimal(0);out=[];refs=set()
        for i,row in enumerate(marks):
            require(isinstance(row,dict) and row.get("currency")==currency,"CURRENCY_MISMATCH")
            at=stamp(row.get("at"));require(prev is None or at>prev,"UNSORTED_OR_DUPLICATE_MARK")
            ref=text(row.get("evidence_ref"));require(ref not in refs,"DUPLICATE_EVIDENCE");refs.add(ref)
            require(row.get("valuation_state")=="RECONCILED_FULL_NAV","NAV_NOT_RECONCILED")
            pre=number(row.get("nav_before_flow"),nonnegative=True);post=number(row.get("nav_after_flow"),nonnegative=True);flow=number(row.get("external_flow"))
            require(pre>0 and post>0 and post-pre==flow,"FLOW_RECONCILIATION_FAILED")
            if i==0:
                require(flow==0,"OPENING_MARK_MUST_HAVE_NO_FLOW");first=post
                period=None
            else:
                period=pre/last-1;index*=1+period;peak=max(peak,index);dd=min(dd,index/peak-1);flows+=flow
            out.append({"at":at.isoformat(),"nav_before_flow":str(pre),"nav_after_flow":str(post),"external_flow":str(flow),
                        "period_return_fraction":None if period is None else str(period),"wealth_index":str(index),"drawdown_fraction":str(index/peak-1),"evidence_ref":ref})
            prev=at;last=post
        return {"schema":SCHEMA,"currency":currency,"opening_nav":str(first),"closing_nav":str(last),"net_external_flows":str(flows),
                "investment_pnl":str(last-first-flows),"twr_fraction":str(index-1),"sampled_max_drawdown_fraction":str(dd),
                "marks":out,"flow_boundary_method":"PRE_POST_EXTERNAL_FLOW","annualized_return":None,"mwr":None,
                "independent_flow_coverage_verified":False,"decision_authorized":False,"order_authorized":False}

def matched_trade(row):
    """One pre-matched, fully closed long lot; no invented matching or FX."""
    require(isinstance(row,dict) and row.get("currency") in ("KRW","USD"),"INVALID_TRADE")
    require(row.get("side")=="LONG" and row.get("lot_state")=="MATCHED_CLOSED","MATCHED_LONG_REQUIRED")
    opened=stamp(row.get("entry_at"));closed=stamp(row.get("exit_at"));thesis=stamp(row.get("thesis_recorded_at"))
    require(thesis<=opened<closed,"THESIS_OR_TRADE_TIME_INVALID")
    for k in ("trade_id","asset_id","thesis_ref","entry_evidence_ref","exit_evidence_ref","exit_reason","review_note"):text(row.get(k),240)
    with localcontext(Context(prec=80)):
        q=number(row.get("quantity"));entry=number(row.get("entry_price"));exit=number(row.get("exit_price"));fees=number(row.get("total_fees"),nonnegative=True)
        require(min(q,entry,exit)>0,"INVALID_TRADE_VALUE")
        cost=q*entry;gross=q*(exit-entry);net=gross-fees
        return {"trade_id":row["trade_id"],"asset_id":row["asset_id"],"currency":row["currency"],
                "entry_at":opened.isoformat(),"exit_at":closed.isoformat(),"quantity":str(q),"entry_price":str(entry),"exit_price":str(exit),
                "gross_price_pnl":str(gross),"total_fees":str(fees),"net_price_pnl_after_fees":str(net),"net_return_on_entry_notional":str(net/cost),
                "thesis_ref":row["thesis_ref"],"thesis_recorded_at":thesis.isoformat(),"exit_reason":row["exit_reason"],"review_note":row["review_note"],
                "dividends_tax_fx_excluded":True,"independent_evidence_verified":False,"decision_authorized":False}

def fixture():
    def mark(i,pre,flow,post):
        return {"at":f"2026-11-{i:02d}T06:00:00+00:00","currency":"KRW","nav_before_flow":str(pre),"external_flow":str(flow),"nav_after_flow":str(post),
                "valuation_state":"RECONCILED_FULL_NAV","evidence_ref":f"fixture:mark:{i}"}
    return [mark(1,1000000,0,1000000),mark(8,1100000,500000,1600000),mark(15,1520000,-200000,1320000),mark(22,1452000,0,1452000)]
def trade_fixture():
    return {"trade_id":"DEMO-01","asset_id":"DEMO_US","side":"LONG","lot_state":"MATCHED_CLOSED","currency":"USD","entry_at":"2026-11-02T14:30:00Z","exit_at":"2026-11-20T14:30:00Z","thesis_recorded_at":"2026-11-01T09:00:00Z",
            "quantity":"10","entry_price":"100","exit_price":"110","total_fees":"2","thesis_ref":"fixture:thesis","entry_evidence_ref":"fixture:entry","exit_evidence_ref":"fixture:exit","exit_reason":"가상 목표가 도달","review_note":"가상 가설과 청산 규칙의 준수 여부 검토"}
def snapshot():
    return {"mode":"SYNTHETIC_ONLY","actual_account_connected":False,"performance":evaluate(fixture(),currency="KRW",scope="FULL_NAV",flow_coverage_confirmed=True),
            "trade":matched_trade(trade_fixture()),"decision_authorized":False,"order_authorized":False}
def render():
    v=snapshot();p=v["performance"];tr=v["trade"]
    def row(a,b):return '<div class="row"><span>'+escape(str(a))+'</span><strong>'+escape(str(b))+'</strong></div>'
    def amount(x):return format(Decimal(x),",.0f")+"원"
    def pct(x):return format(Decimal(x)*100,"+.2f")+"%"
    out=['<p class="notice"><strong>합성 성과 / 실제 계좌 아님</strong> · 모든 자산과 현금이 확인된 NAV 가정. 입출금 직전·직후 평가액이 있는 경우에만 계산.</p>',
         '<div class="section">01 / PERFORMANCE</div>',row("기초 NAV",amount(p["opening_nav"])),row("기말 NAV",amount(p["closing_nav"])),row("순입금",amount(p["net_external_flows"])),row("투자 손익",amount(p["investment_pnl"])),
         row("시간가중수익률 TWR",pct(p["twr_fraction"])),row("표본 최대낙폭",pct(p["sampled_max_drawdown_fraction"]))]
    values=[float(x["wealth_index"]) for x in p["marks"]];lo=min(values);span=max(values)-lo or 1
    pts=" ".join(f"{10+i*300/(len(values)-1):.1f},{70-60*(z-lo)/span:.1f}" for i,z in enumerate(values))
    out.append('<svg viewBox="0 0 320 80" role="img" aria-label="입출금 제거 합성 자산지수" style="width:100%;height:auto"><polyline points="'+pts+'" fill="none" stroke="#333" stroke-width="1.4"/></svg>')
    out.append('<p class="notice">관측 시점만으로 계산한 낙폭. 장중 최대낙폭·연환산·금액가중수익률 미계산.</p><div class="section">02 / CASH FLOW BOUNDARIES</div>')
    for x in p["marks"]:out.append(row(x["at"][:10]+" / 입출금 "+amount(x["external_flow"]),amount(x["nav_after_flow"])))
    out.extend(['<div class="section">03 / TRADE REVIEW · SYNTHETIC</div>',row("종목",tr["asset_id"]),row("진입/청산",tr["entry_price"]+" / "+tr["exit_price"]+" USD"),row("수수료 제외 전 가격 손익",tr["gross_price_pnl"]+" USD"),row("수수료 차감 가격 손익",tr["net_price_pnl_after_fees"]+" USD"),row("청산 사유",tr["exit_reason"]),row("복기",tr["review_note"]),'<p class="notice">이미 대응시킨 완결된 매수/매도 로트만 처리. 배당·세금·FX 제외, 실제 매매 원장/증빙 미연결. 보유증권 평가액 또는 매수가능금액으로 NAV를 추정하지 않습니다.</p>'])
    return "".join(out)

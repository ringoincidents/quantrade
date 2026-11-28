"""Explicit synthetic portfolio scenarios, never real holdings."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, Context, localcontext
from html import escape
from portfolio_projection import collect, SnapshotCache

SCENARIOS={"initial","event","reconciled","failed","stale"}
AT=datetime(2026,11,28,0,0,tzinfo=timezone.utc)

def read_fixture(path,account=None,params=None,*,updated=False):
    if path=="/api/v1/accounts":
        return [{"accountSeq":"101"},{"accountSeq":"102"}]
    if path=="/api/v1/holdings":
        kr=account=="101"
        qty=2 if kr else (4 if updated else 3)
        price=Decimal("120000") if kr else Decimal("100")
        return {"hasNext":False,"items":[{"symbol":"DEMO_KR" if kr else "DEMO_US",
          "name":"가상 국내 종목" if kr else "가상 해외 종목","currency":"KRW" if kr else "USD",
          "quantity":str(qty),"lastPrice":str(price),"averagePurchasePrice":str(price),
          "marketValue":{"amount":str(price*qty)},"profitLoss":{"amount":"0","rate":"0"}}]}
    if path=="/api/v1/buying-power":
        return {"cashBuyingPower":"500000" if params["currency"]=="KRW" else "250"}
    if path=="/api/v1/exchange-rate":
        return {"rate":"1400"}
    raise ValueError("UNKNOWN_FIXTURE_ROUTE")

def scenario(name):
    if name not in SCENARIOS:
        raise ValueError("UNKNOWN_FIXTURE")
    c=SnapshotCache()
    t=c.begin()
    c.finish(t,collect(read_fixture,lambda:AT))
    if name in ("event","reconciled","failed"):
        c.invalidate()
    if name=="reconciled":
        t=c.begin()
        c.finish(t,collect(lambda p,**kw:read_fixture(p,updated=True,**kw),lambda:AT+timedelta(seconds=30)))
    if name=="failed":
        c.fail(c.begin())
    at=AT+timedelta(minutes=6) if name=="stale" else AT+timedelta(seconds=30)
    v=c.view(at)
    v["mode"]="SYNTHETIC_ONLY"
    v["scenario"]=name
    v["last_observation"]["source"]="SYNTHETIC_FIXTURE"
    v["actual_account_connected"]=False
    return v

def fmt(value,places=2):
    if value is None:
        return "—"
    with localcontext(Context(prec=80)):
        return format(Decimal(value),",."+str(places)+"f")

def render(name):
    v=scenario(name)
    o=v["last_observation"]
    status={"OBSERVED":"조회 완료","RECONCILIATION_REQUIRED":"재조회 필요","REFRESH_FAILED":"조회 실패","STALE":"오래된 자료"}[v["state"]]
    out=['<p class="notice"><strong>합성 데이터 / 실제 계좌 아님</strong> · 이 화면의 숫자는 임의로 만든 검증 자료입니다.</p>',
         '<div class="row"><span>동기화 상태</span><strong>'+status+'</strong></div>',
         '<p class="notice">관측 시각 '+escape(o["finished_at"])+' · '+("현재 합성 관측" if v["current_observation"] else "이전 관측 참고 전용 / 현재값 아님")+'</p>',
         '<div class="section">01 / SECURITIES</div><div class="row"><span>보유증권 평가액 (원화 환산)</span><strong>₩'+fmt(o["securities_value_krw"],0)+'</strong></div>',
         '<div class="row"><span>순자산 / 실제 현금</span><strong>미확인</strong></div>']
    for a in o["accounts"]:
        out.append('<div class="section">ACCOUNT '+str(a["snapshot_account_index"])+' / 가상 계좌</div>')
        out.append('<div class="row"><span>매수 가능 금액 (현금과 별도)</span><strong>₩'+fmt(a["buying_power"]["KRW"],0)+' / $'+fmt(a["buying_power"]["USD"])+'</strong></div>')
        for h in a["holdings"]:
            weight=fmt(Decimal(h["securities_weight_fraction"])*100) if h["securities_weight_fraction"] is not None else "—"
            out.append('<div class="row"><span>'+escape(h["name"])+'<br><small>'+escape(h["symbol"])+' · '+fmt(h["quantity"],2)+'주</small></span><strong>'+escape(h["currency"])+' '+fmt(h["market_value"])+'<br><small>보유증권 내 '+weight+'%</small></strong></div>')
            out.append('<div class="row"><span>현재가 / 평단 (관측값)</span><strong>'+fmt(h["last_price"])+' / '+fmt(h["average_purchase_price"])+'</strong></div>')
    out.append('<div class="section">02 / RECONCILIATION SCENARIOS</div>')
    for key,label in [("initial","최초 조회"),("event","주문 이벤트 수신"),("reconciled","재조회 완료"),("failed","조회 실패"),("stale","시간 경과")]:
        out.append('<div class="row"><a href="/assets/demo/'+key+'">'+label+'</a>'+("<strong>선택</strong>" if key==name else "")+'</div>')
    out.append('<p class="notice">각 링크는 독립적인 합성 실험입니다. 실제 주문이나 API 요청은 발생하지 않습니다.</p><p><a href="/assets">실계좌 원장으로 돌아가기</a></p>')
    return "".join(out)

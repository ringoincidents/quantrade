"""Synthetic-only chart and mechanics comparator; pinned Vault code."""
from datetime import date,timedelta
from functools import lru_cache
from html import escape
import math
from feature_bridge import measure_bars
from indicators import sma,LIBRARY_VERSION
from multiframe import bounds
PIN="35e3ec0059de2f81c50bfd9a6ebedc819109b42c"
FRAMES={"D":"일봉","W":"주봉","M":"월봉","Y":"년봉"}

@lru_cache(maxsize=1)
def daily():
    a=date(2010,1,1);z=date(2025,12,31);out=[]
    for i in range((z-a).days+1):
        day=a+timedelta(days=i)
        if day.weekday()>=5:continue
        j=len(out);c=100+.025*j+8*math.sin(j/25)+3*math.sin(j/7)
        o=c+1.5*math.sin(j/3);h=max(c,o)+1;l=min(c,o)-1
        out.append({"session":day.isoformat(),"open":o,"high":h,"low":l,"close":c,"volume":1000+100*math.sin(j/9)})
    return tuple(out)
@lru_cache(maxsize=4)
def series(frame):
    if frame not in FRAMES:raise ValueError("UNKNOWN_FRAME")
    raw=daily()
    if frame=="D":return raw
    # Synthetic display uses same calendar period grouping rule as Vault.
    # Full fixture calendar date coverage, not exchange sessions.
    groups={}
    for r in raw:
        a,z=bounds(date.fromisoformat(r["session"]),frame)
        if a<date(2010,1,1) or z>date(2025,12,31):continue
        groups.setdefault((a,z),[]).append(r)
    return tuple({"session":z.isoformat(),"open":g[0]["open"],"high":max(r["high"] for r in g),
        "low":min(r["low"] for r in g),"close":g[-1]["close"],"volume":math.fsum(r["volume"] for r in g)} for (a,z),g in groups.items())

def lab(frame):
    rows=series(frame);p=[r["close"] for r in rows]
    measures=measure_bars(rows,"DEMO")
    lines={str(n):sma(p,n)[-64:] for n in (5,20,60)}
    return {"mode":"SYNTHETIC_ONLY","instrument":"DEMO","frame":frame,"input_count":len(rows),"bars":list(rows[-64:]),
        "ma":lines,"features":measures,"vault_revision":PIN,"library_version":LIBRARY_VERSION,
        "actual_data_connected":False,"decision_authorized":False,"order_authorized":False}

def svg(v):
    rows=v["bars"];n=len(rows);lo=min(r["low"] for r in rows);hi=max(r["high"] for r in rows)
    for line in v["ma"].values():
        vals=[x for x in line if x is not None]
        if vals:lo=min(lo,min(vals));hi=max(hi,max(vals))
    span=hi-lo or 1
    x=lambda j:18+j*304/max(1,n-1)
    y=lambda val:10+140*(hi-val)/span
    out=['<svg viewBox="0 0 340 180" role="img" aria-label="합성 캔들 및 이동평균선" style="width:100%;height:auto">']
    for j,r in enumerate(rows):
        c="#a33131" if r["close"]>=r["open"] else "#315d83"
        out.append(f'<line x1="{x(j):.2f}" x2="{x(j):.2f}" y1="{y(r["high"]):.2f}" y2="{y(r["low"]):.2f}" stroke="{c}"/><rect x="{x(j)-1.5:.2f}" y="{min(y(r["open"]),y(r["close"])):.2f}" width="3" height="{max(1,abs(y(r["open"])-y(r["close"]))):.2f}" fill="{c}"/>')
    for (k,line),c in zip(v["ma"].items(),("#ad7b25","#3d6655","#625b83")):
        pts=" ".join(f"{x(j):.2f},{y(z):.2f}" for j,z in enumerate(line) if z is not None)
        if pts:out.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="1.2"/>')
    out.append('<text x="12" y="170" font-size="10">'+rows[0]["session"]+'</text><text x="250" y="170" font-size="10">'+rows[-1]["session"]+'</text></svg>')
    return "".join(out)
def row(a,b):return '<div class="row"><span>'+escape(str(a))+'</span><strong>'+escape(str(b))+'</strong></div>'
def render_lab(frame):
    v=lab(frame);out=['<p class="notice"><strong>합성 차트 / 실제 종목 아님</strong> · DEMO · 임의 생성 시계열</p>',
        '<p class="section">'+ " · ".join('<a href="/lab/'+k+'">'+label+'</a>' for k,label in FRAMES.items())+'</p>',svg(v),
        '<p class="notice">SMA 5 / 20 / 60 · 최근 최대 64봉 표시. 데이터 부족 시 계산하지 않음.</p>',row("시간봉",FRAMES[frame]),row("전체 입력 봉",v["input_count"])]
    for k in ("SMA:5","SMA:20","SMA:60","DISPARITY:25","RSI:WILDER:14","ATR:WILDER:14","CMF:20","MA_WIDTH:5:20:60","PRICE_GEOMETRY:distance_to_prior_high"):
        f=v["features"][k];out.append(row(k,"계산 부족" if f["value"] is None else f'{f["value"]:.4f} · {f["unit"]}'))
    out.append('<p><a href="/strategies">전략 비교 / 합성 실험</a></p>')
    return "".join(out)

@lru_cache(maxsize=1)
def compare():
    rows=daily();p=[r["close"] for r in rows];m25=sma(p,25);m5=sma(p,5);m20=sma(p,20)
    result=[]
    for label,kind in (("25봉 이격도 ≤95","DISPARITY"),("5봉선 >20봉선","TREND"),("고정 간격 기준","BASELINE")):
        rs=[];i=25
        while i+6<len(rows):
            yes=(100*p[i]/m25[i]<=95 if kind=="DISPARITY" else m5[i]>m20[i] if kind=="TREND" else i%20==0)
            if not yes:i+=1;continue
            # Signal at close, enter next open; exit five sessions later at open.
            entry=rows[i+1]["open"];exit=rows[i+6]["open"]
            rs.append(exit*(1-.001)/(entry*(1+.001))-1);i+=6
        result.append({"label":label,"kind":kind,"events":len(rs),"mean_net_event_return":sum(rs)/len(rs) if rs else None,
           "win_fraction":sum(x>0 for x in rs)/len(rs) if rs else None})
    return {"mode":"SYNTHETIC_MECHANICS_ONLY","results":result,"holding_sessions":5,"one_way_cost_fraction":.001,
        "entry":"NEXT_OPEN","exit":"OPEN_AFTER_5_SESSIONS","actual_backtest":False,"decision_authorized":False,"order_authorized":False}
def render_compare():
    v=compare();out=['<p class="notice"><strong>합성 실험 / 실제 백테스트 아님</strong> · 임의 조건, 기존 전략 원문 재현 아님. 종가 확인 후 다음 시가 진입, 5봉 후 시가 청산, 편도 비용 0.1% 가정.</p>']
    for r in v["results"]:
        out.append('<div class="section">'+escape(r["label"])+'</div>')
        out.append(row("사건 수",r["events"]))
        out.append(row("평균 사건 순수익률","—" if r["mean_net_event_return"] is None else f'{r["mean_net_event_return"]*100:.2f}%'))
        out.append(row("양수 사건 비율","—" if r["win_fraction"] is None else f'{r["win_fraction"]*100:.1f}%'))
    out.append('<p class="notice">사건 수익률 비교이며 복리 포트폴리오 수익률이 아님. 실제 BNF·주식챠트교육·QT-MRI 채택 및 실증은 G0 차단.</p>')
    return "".join(out)

"""Read-only F08 demo from the exact pinned workbench implementation.
No arbitrary document import, live valuation, price access or approval mutation.
"""
from decimal import Decimal, Context, localcontext
from html import escape
from quantrade.workbench.local_report import demo, evaluate, digest

WORKBENCH_REV="f64b61c088a8e17cb04617f95d4f458671bea602"
SCENARIOS={"baseline","revised","revoked","expired"}
LABELS={"baseline":"기준 사례","revised":"수정 종가","revoked":"승인 철회","expired":"승인 만료"}
REASONS={"ENTRY_CONDITION_MET":"검토 조건 충족","ABOVE_ENTRY":"진입 기준가 초과",
         "MISSING_QUOTE":"종가 없음","TARGET_NOT_CURRENT":"유효한 승인 없음",
         "SESSION_MISMATCH":"거래일 불일치","INVALID_PRICE":"가격 오류"}
STATES={"REVIEW":"검토 후보","WAIT":"대기","BLOCKED":"판정 차단"}

def scenario(name):
    if name not in SCENARIOS:
        raise ValueError("UNKNOWN_SCENARIO")
    doc=demo()
    if name=="revised":
        q=dict(doc["quotes"][0])
        q.update(revision=2,price="81.00",source_ref="synthetic-correction")
        doc["quotes"].append(q)
    if name=="revoked":
        t=doc["targets"][0]
        doc["revocations"].append({"ref":"fixture-revoke","operator":"SYNTHETIC",
               "target_hash":digest(t),"revoked_at":doc["as_of"]})
    if name=="expired":
        doc["as_of"]="2027-01-01T00:00:00+09:00"
    report=evaluate(doc)
    return {"mode":"SYNTHETIC_ONLY","scenario":name,"workbench_revision":WORKBENCH_REV,
            "decision_authorized":False,"order_authorized":False,
            "actual_data_connected":False,"report":report}

def fmt(v,places=2,percent=False):
    if v is None:
        return "—"
    with localcontext(Context(prec=80)):
        return format(Decimal(v)*(100 if percent else 1),",."+str(places)+"f")+("%" if percent else "")

def render(name):
    v=scenario(name); r=v["report"]
    out=['<p class="notice"><strong>합성 데이터 / 실제 매수 신호 아님</strong> · 기존 F08 계산 엔진의 고정 사례입니다.</p>',
         '<div class="row"><span>관측 기준</span><strong>'+escape(r["as_of"])+'</strong></div>',
         '<div class="row"><span>데이터 검증</span><strong>합성 입력 선언</strong></div>']
    for status in ("REVIEW","BLOCKED","WAIT"):
        out.append('<div class="row"><span>'+STATES[status]+'</span><strong>'+str(sum(x["status"]==status for x in r["rows"]))+'</strong></div>')
    for row in r["rows"]:
        out.extend(['<div class="section">'+escape(row["instrument"])+' / '+STATES[row["status"]]+'</div>',
          '<div class="row"><span>판정 사유</span><strong>'+escape(REASONS.get(row["reason"],row["reason"] or "미확인"))+'</strong></div>',
          '<div class="row"><span>종가 / 진입 기준가 ('+escape(row["currency"])+')</span><strong>'+fmt(row["price"])+' / '+fmt(row["entry_price"])+'</strong></div>',
          '<div class="row"><span>안전마진 / 기준가 대비 차이</span><strong>'+fmt(row["safety_margin"],percent=True)+' / '+fmt(row["gap"],percent=True)+'</strong></div>',
          '<div class="row"><span>거래일 / 승인 버전</span><strong>'+escape(row["session_date"] or "—")+' / '+escape(row["target_version"] or "—")+'</strong></div>',
          '<p class="notice">출처: '+escape(row["source"] or "없음")+' · 승인 유효기간: '+escape(row["expires_at"] or "—")+'</p>'])
    out.append('<div class="section">02 / FIXED SCENARIOS</div>')
    for k in ("baseline","revised","revoked","expired"):
        out.append('<div class="row"><a href="/reports/demo/'+k+'">'+LABELS[k]+'</a>'+("<strong>선택</strong>" if k==name else "")+'</div>')
    out.append('<p class="notice">엔진 기준 커밋 '+WORKBENCH_REV[:12]+' · 실제 종가, 승인 및 데이터 권리 검증 전. 주문 기능 없음.</p><p><a href="/reports">보고서 대장으로 돌아가기</a></p>')
    return "".join(out)

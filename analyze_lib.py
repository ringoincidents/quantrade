import argparse
import requests
import math
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

EXCLUDE_MARKETS = {"KRW-USDT", "KRW-USDC", "KRW-USDE", "KRW-USDS", "KRW-DAI"}
US_STOCKS = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]
POSITIVE_WORDS = ["surge", "rally", "gain", "bullish", "record", "growth", "beat", "strong"]
NEGATIVE_WORDS = ["crash", "plunge", "bearish", "loss", "fall", "concern", "risk", "weak", "drop"]
HARD_STOP_LOSS = {"단타": -5, "스윙": -10, "장기": -25}

# 포지션 사이징(2026-08-01 설계 확정). 라이브(analyze.py의 needs_approval)와
# 백테스트(backtest.py의 MDD 재계산)가 같은 숫자를 쓰도록 여기 한 곳에만 둔다.
# - AUTO_TIER_WEIGHT 미만: 자동 실행
# - AUTO_TIER_WEIGHT 이상: 사람 승인 필요
# - POSITION_WEIGHT_HARD_CAP 초과: 승인해도 차단(하드 상한, 매수 금액을 이 비중으로 clamp)
# 기존 LARGE_POSITION_THRESHOLD(0.25, 승인만 필요·상한 없음)를 대체 — 백테스트 gate가
# 명확히 미통과한 상태에서 자산 대부분을 검증 안 된 판단에 거는 걸 막기 위해 강화했다.
AUTO_TIER_WEIGHT = 0.10
POSITION_WEIGHT_HARD_CAP = 0.20

# 종합계획서 v3 §2 "거래비용/슬리피지가 백테스트 계산에서 빠져 있음" 대응.
# 매수/매도 각각에 편도로 적용되는 가정치(%) — 왕복 시 두 번 적용됨.
# 실측치 확보 전까지의 잠정 가정이며, 백테스트 결과 해석 시 이 가정에 의존한다는 점을 감안할 것.
TRADING_COSTS = {
    "crypto": {"fee_pct": 0.05, "slippage_pct": 0.1},   # 업비트 매수/매도 수수료 0.05%(실측) + 가정 슬리피지
    "krx": {"fee_pct": 0.015, "slippage_pct": 0.1, "sell_tax_pct": 0.18},
        # 토스증권 온라인 수수료(매수/매도 각 0.015%) + 가정 슬리피지 + 매도 시에만 붙는
        # 증권거래세+농특세(코스피 기준 약 0.18%; 코스닥은 이보다 낮지만 보수적으로 통일)
    "stock": {"fee_pct": 0.25, "slippage_pct": 0.1},    # 해외주식 매매수수료 가정치 + 슬리피지 (SEC 수수료 등은 미미해 생략)
}

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")

# 실계좌(토스) AI 제안 dry-run 게이트 (2026-08-01, 2026-08-02 TRACK_B_ENABLED에서 리네이밍).
# True(기본값)인 동안 ask_claude_decision은 real_portfolio.json 보유종목을 계속 참고해
# 매도/비중조정 제안을 만들지만, 그 제안은 pending_actions.json에 dry_run: true로만
# 기록되고 /approve를 눌러도 실제로는 아무것도 실행되지 않는다(실계좌엔 애초에 주문
# API가 없다 — CLAUDE.md "조회 전용" 원칙). 10월 말 게이트 통과 판정(claude.ai
# 방향성 세션) 전까지 이 값을 false로 바꾸지 말 것.
#
# 이름에 "TRACK_B"를 쓰지 않는 이유: CLAUDE.md가 "Track B"를 이미 별개의, 더 엄격한
# 의미(실주문 코드 + 자동트리거가 둘 다 존재하는 실거래 자동화 상태)로 정의해뒀다.
# TRACK_B_ENABLED라는 이름은 나중에 그 실제 마스터 스위치용으로 예약해두고, 지금은
# 만들지 않는다 — 아직 실주문 코드 자체가 없어서 그 스위치가 가리킬 대상이 없다.
AI_SUGGESTION_DRY_RUN = os.environ.get("AI_SUGGESTION_DRY_RUN", "true").lower() == "true"

# ─────────────────────────────────────────────────────────────────────────────
# v3.2 전환 (2026-08-03) — 예측 경로 마스터 스위치.
#
# **기각된 연구 결과, 활성 기능 제외.** 가격 신호(entry_score/scan_* 계열)와 뉴스
# 방향 판단이 둘 다 §2.1 게이트를 통과하지 못했다. 특히 뉴스 방향 판단은 단순
# 다수클래스 baseline보다도 적중률이 낮았고, 방향별 적중률이 기저비율과 사실상
# 동일해(D+1 호재 40.0% vs 기저 40.1%) 방향 판단에 정보가 없다는 결론이 나왔다.
# 근거: Phase2_과거뉴스백테스트_설계.md §8, CLAUDE.md 최상단 v3.2 절.
#
# 이 값이 False인 동안:
#   - 후보 스캔(scan_crypto/scan_stocks)과 ask_claude_decision을 호출하지 않는다.
#   - AI 기반 매수/매도/비중조정 결정이 생성되지 않는다(가상·실계좌 양쪽 모두).
#   - 하드 손절 등 **규칙 기반 가드레일은 계속 동작한다** — 그건 예측이 아니라
#     사전에 정해진 규칙의 산술 판정이라 이번 기각과 무관하다.
#
# **코드는 삭제하지 않았다.** 재개하려면 다시 §2.1 게이트를 통과해야 하고, 그때
# 이 스위치를 되돌린다. 프롬프트를 고쳤다거나 이번엔 될 것 같다는 이유로 켜지 마라.
PREDICTION_ENABLED = os.environ.get("PREDICTION_ENABLED", "false").lower() == "true"

# ─────────────────────────────────────────────────────────────────────────────
# 규칙 기반 포지션 관리 자동실행 (2026-08-04, 방향성 세션 정식 승인).
#
# **TRACK_B_ENABLED와는 별개의 플래그이며, 코드 상 두 플래그 사이에 어떤 참조
# 관계도 없다** — 한쪽 값이 다른 쪽을 읽거나 바꾸지 않고, 서로의 조건문에
# 등장하지도 않는다. (TRACK_B_ENABLED는 아직 정의돼 있지도 않은 예약된 이름이다.)
# 혼동 방지를 위해 명시해 둔다.
#
# 이 플래그가 켜지면 autoexec.py의 세 규칙(집중도 리밸런싱 / 손실 지속 손절 /
# 목표가 부분익절)이 **매도만** 실행한다. 매수 경로는 코드 구조상 없다.
#
# 활성화 순서(방향성 세션 지시, 건너뛰지 말 것):
#   1) /autoexec_stop 킬스위치 테스트 통과
#   2) 안전장치(전량 로깅/사후 통보/유예기간 레이트리밋) 전부 검증
#   3) 그 다음에만 이 값을 true로
#
# 현재 주문 실행 계층(autoexec.place_sell_order)은 토스 주문 API 스펙이 없어
# 미구현이다. 따라서 이 값을 true로 바꿔도 주문은 나가지 않고 "실행 불가"로
# 로깅된다.
RULE_BASED_AUTOEXEC_ENABLED = os.environ.get("RULE_BASED_AUTOEXEC_ENABLED", "false").lower() == "true"

# ─────────────────────────────────────────────────────────────────────────────
# 자유텍스트 요약/설명을 만드는 여러 모듈(rule_trigger_report.py, news_event_cards.py,
# market_indicators.py, post_trade_review.py, portfolio_report.py,
# indicator_significance_test.py, analyze.py)이 공유하는 금지 필드/문구 기본
# 세트다(2026-08-10, 방향성 세션 지시 "자유텍스트 금지문구 전수 점검").
#
# 각 파일이 이 목록을 따로 복사해 갖고 있다가, news_event_cards.py 한 곳에서만
# "목표주가"가 빠져 있어 실제로 커밋된 파일에 새어나간 적이 있다(post_trade_review.py
# 개발 중 발견, 같은 커밋에서 수정) — 반복될 수 있는 종류의 드리프트라 공통 부분만
# 이라도 한 곳에서 관리한다. **이 목록만으로 충분하다고 가정하지 않는다** — 맥락마다
# 위험한 문구가 다를 수 있어 각 모듈이 자기 맥락에 맞는 항목을 추가로 더한다(예:
# market_indicators.py는 "국면 전환"/"상승장" 같은 국면 판별 관련 문구를, post_trade_review.py는
# 반대로 사실 서술에 필요한 "매수"/"매도" 단독 표현은 기본 세트에서 빼고 쓴다 — 이미
# 일어난 매매를 "그 사이 매도 없이 보유가 유지" 식으로 서술해야 하는데, 이 기본
# 세트는 명령형("매도하세요")만 막고 명사형은 각 모듈이 선택하도록 남겨둔다).
FORBIDDEN_PHRASES_BASE = (
    "매수하세요", "매도하세요", "사세요", "파세요",
    "추천", "권장", "권합니다",
    "유망", "저평가", "고평가", "목표가", "목표주가",
    "상승 전망", "하락 전망", "전망됩니다", "예상됩니다", "기대됩니다", "판단됩니다",
    "지금이 기회", "그래서 사도", "팔아야",
    "1위", "순위",
)
FORBIDDEN_FIELDS_BASE = (
    "direction", "confidence", "action", "recommendation",
    "signal", "buy", "sell", "score", "target_weight_pct", "rating",
    "rank", "ranking", "phase", "regime", "grade", "color", "colour",
)


def normalize_path(path):
    """배열 인덱스를 지워 경로 패턴으로 만든다(A2_Intelligence_Layer_Design.md
    §3-3). 'report.change_events[3].priority.priority_score' ->
    'report.change_events[].priority.priority_score' — allowed_paths에는
    인덱스 없는 패턴만 등록하면 되고, 배열 길이가 달라져도(이벤트가 몇 건이든)
    같은 패턴으로 매치된다."""
    return re.sub(r"\[\d+\]", "[]", path)


def audit_schema(obj, path="report", allowed_paths=frozenset()):
    """FORBIDDEN_FIELDS_BASE/FORBIDDEN_PHRASES_BASE 재귀 검사 — 각 생성기의
    audit()(rule_trigger_report.py/market_indicators.py/news_event_cards.py에
    거의 동일하게 복붙돼 있음)과 같은 패턴이되, 위반 예외를 **파일 전체에서
    단어를 통째로 면제**하는 대신 **정확한 필드 경로 하나만** 면제할 수 있다
    (§3-3). "우연히 정확일치를 피해감"에 기대지 않고 "이 정확한 위치는 검토
    후 허용됨"을 코드에 남기는 장치 — 같은 필드명이 다른 위치에 새로 나타나면
    여전히 걸린다.

    2026-08-29 PM 확정: 신규 예외는 이 경로단위 방식만 쓴다. 기존 파일단위
    예외(indicator_significance_test.py의 signal, portfolio_report.py의
    rank/ranking)는 소급 전환하지 않는다 — 이 함수를 쓰지 않고 그대로 둔다."""
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            field_path = f"{path}.{k}"
            if k.lower() in FORBIDDEN_FIELDS_BASE and normalize_path(field_path) not in allowed_paths:
                bad.append(f"{field_path} (금지 필드)")
            bad += audit_schema(v, field_path, allowed_paths)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += audit_schema(v, f"{path}[{i}]", allowed_paths)
    elif isinstance(obj, str):
        for ph in FORBIDDEN_PHRASES_BASE:
            if ph in obj:
                bad.append(f"{path}: 금지 문구 '{ph}'")
    return bad


# ─────────────────────────────────────────────────────────────────────────────
# A2 Intelligence Layer 공통 이벤트 스키마 (2026-08-29, A2_Intelligence_Layer_Design.md
# 최종본 Step 1 구현, PM 지시 "A2 코드 구현 착수" §1 그대로).
#
# Change Detection(Step 2)/Prioritization(Step 3)/Portfolio Relevance(Step 4)가
# 공유하는 9개 필드 정의. 이 스키마가 먼저 굳어야 나머지 단계가 뒤집히지
# 않는다는 게 PM 지시 원문 — 그래서 이 블록만 별도로 self-test하고 먼저
# 중간보고한다.
#
# **이 스키마는 news_event_cards.py의 카드 스키마(CARD_FIELDS)를 대체하지
# 않는다.** 카드(뉴스 사건 설명/이상행동)는 계속 별도 화이트리스트로 대시보드에
# 표시된다 — 공통 스키마는 Change Detection이 새로 만드는 change_events[] 배열
# 안의 객체 형태다(설계 문서 §1-4 예시 그대로: 각 생성기 JSON의 최상위
# generated_at/schema는 그대로 두고, 그 아래 change_events[]에 이 스키마를
# 따르는 항목을 추가하는 방식).
# ─────────────────────────────────────────────────────────────────────────────

# event_type 허용값(설계 문서 §2-3). ACTIVE 4종은 이번 A2에서 실제 계산식이
# 있는 대상(Step 2가 만들어낸다), RESERVED 2종은 v4.0 로드맵 Phase B(B2/B4)
# 대기 — 스키마에 자리만 예약하고 계산 로직은 만들지 않는다(설계 문서 §1-1/
# §2-3 "계산식 설계는 보류"). validate_common_event는 RESERVED 값도 유효한
# event_type으로 받아들이지만(자리 예약이 스키마 목적), Step 2 코드가 이
# 값을 실제로 만들어내지는 않는다.
EVENT_TYPE_ACTIVE = ("거래량_급증", "변동성_급증", "가격_갭", "상관관계_변화")
EVENT_TYPE_RESERVED = ("환율_급변", "뉴스빈도_급증")  # Phase B 대기 - 계산 미설계
EVENT_TYPE_ENUM = EVENT_TYPE_ACTIVE + EVENT_TYPE_RESERVED

# source 식별자 레지스트리(§1-2 "5개 생성기 출력 → 공통 스키마 매핑표"를 코드로도
# 남긴 것). "<모듈>.<방법>" 형태 — 방법 단위까지 구분하는 이유는 Step 3의
# Reliability 산정이 소스별로 다른 고정값을 쓰기 때문(§3-1). 값은 사람이 읽는
# 설명일 뿐 검증에 쓰이지 않는다 — source는 자유 문자열이고 이 레지스트리는
# "이미 정의된 것들"의 목록이지 화이트리스트가 아니다(신규 소스 추가를 막지
# 않음). post_trade_review.py/portfolio_report.py/rule_trigger_report.py는
# 아직 change_events를 만들지 않지만(Step 2는 news_event_cards.py/
# market_indicators.py만 통합), §1-2 매핑표가 5개 생성기 전부를 다루므로
# 여기서도 5개 전부의 식별자를 남겨 나중에 그 매핑표를 다시 찾아볼 필요가
# 없게 한다.
COMMON_EVENT_SOURCES = {
    "news_event_cards.ai_summary": "뉴스 사건 설명 카드(AI 요약, Claude 판단 개입)",
    "news_event_cards.anomaly": "이상행동 카드(산술 판정, AI 미개입)",
    "market_indicators.state_board": "시장 상태 수치판 스냅샷(변동성 백분위/ADX)",
    "portfolio_report.rule_matches": "포트폴리오 리포트 규칙 매치(집중도/손실지속/목표가)",
    "post_trade_review.correlation_blind_spots": "매매 후 리뷰 - 상관관계 사각지대 섹션",
    "rule_trigger_report.trigger": "규칙 발동 심층분석 리포트 - 발동 사실 섹션",
}

# 9개 필드 정의(§1-1). required=True는 무조건 있어야 하는 필드(None이면 위반),
# required="conditional"은 observed_value/baseline/change처럼 이벤트 종류에
# 따라 null이 정상인 필드(순수 뉴스 사건은 수치가 없음 — §1-1).
COMMON_EVENT_SCHEMA = {
    "timestamp":      {"required": True,        "type": str,          "nullable": False},
    "asset":          {"required": True,        "type": dict,         "nullable": False},
    "source":         {"required": True,        "type": str,          "nullable": False},
    "event_type":     {"required": True,        "type": str,          "nullable": False},
    "observed_value": {"required": "conditional", "type": (int, float), "nullable": True},
    "baseline":       {"required": "conditional", "type": (int, float), "nullable": True},
    "change":         {"required": "conditional", "type": (int, float), "nullable": True},
    "reliability":    {"required": True,        "type": (int, float), "nullable": False},
    "related_assets": {"required": True,        "type": list,         "nullable": False},
}

ASSET_REQUIRED_KEYS = ("symbol", "name", "market_country", "currency")
RELATED_ASSET_RELATIONS = ("correlation_pair", "portfolio_holding", "watchlist")


def _is_iso8601_utc(value):
    """ISO 8601, UTC, 오프셋 포함 형식인지 가볍게 확인(§1-1). 완전한 RFC 검증이
    아니라 "오프셋이 없는 naive 문자열이 섞이는" 사고를 잡는 정도의 점검이다
    — rule_trigger_report.py가 실제로 겪었던 문제(§1-3)가 스키마 검증에서도
    조용히 통과하지 않게 한다."""
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "+" in value[10:] or value.endswith("Z") or "-" in value[19:]


def build_common_event(*, timestamp, asset, source, event_type, reliability,
                        observed_value=None, baseline=None, change=None,
                        related_assets=None):
    """9개 필드 스키마를 따르는 이벤트 객체 하나를 만든다(§1-1). 필수값 누락/
    잘못된 타입/허용 밖 event_type이면 즉시 ValueError로 막는다 — 생성 시점에
    막는다는 점이 각 생성기의 audit()(사후 검사, 위반을 태그만 달거나 저장을
    거부)과 다르다: 이건 애초에 스키마를 어긴 이벤트 객체가 만들어지지 않게
    한다. Step 2(Change Detection)가 이 함수로 change_events[] 항목을 만든다."""
    event = {
        "timestamp": timestamp,
        "asset": asset,
        "source": source,
        "event_type": event_type,
        "observed_value": observed_value,
        "baseline": baseline,
        "change": change,
        "reliability": reliability,
        "related_assets": related_assets if related_assets is not None else [],
    }
    errors = validate_common_event(event)
    if errors:
        raise ValueError(f"공통 이벤트 스키마 위반: {errors}")
    return event


def validate_common_event(event, path="event"):
    """스키마 위반 목록을 반환(빈 리스트 = 위반 없음). 각 생성기의 audit()류
    함수와 같은 "예외를 던지지 않고 위반을 모아 반환"하는 패턴 — 호출자가
    build_common_event처럼 즉시 raise할지, 다른 소비자처럼 위반을 태그만
    남기고 계속 진행할지 선택할 수 있게 한다."""
    errors = []
    if not isinstance(event, dict):
        return [f"{path}: dict가 아님"]

    for field, spec in COMMON_EVENT_SCHEMA.items():
        present = field in event and event[field] is not None
        if not present:
            if spec["required"] is True:
                errors.append(f"{path}.{field}: 필수 필드 누락")
            continue
        value = event[field]
        if not isinstance(value, spec["type"]):
            errors.append(f"{path}.{field}: 타입 오류(기대 {spec['type']}, 실제 {type(value)})")

    if event.get("event_type") is not None and event["event_type"] not in EVENT_TYPE_ENUM:
        errors.append(f"{path}.event_type: 허용되지 않은 값 '{event.get('event_type')}' "
                       f"(허용: {EVENT_TYPE_ENUM})")

    if event.get("timestamp") is not None and not _is_iso8601_utc(event["timestamp"]):
        errors.append(f"{path}.timestamp: ISO 8601 UTC(오프셋 포함) 형식이 아님 "
                       f"('{event.get('timestamp')}')")

    reliability = event.get("reliability")
    if isinstance(reliability, (int, float)) and not (0.0 <= reliability <= 1.0):
        errors.append(f"{path}.reliability: 0.0~1.0 범위 밖 ({reliability})")

    asset = event.get("asset")
    if isinstance(asset, dict):
        missing_asset_keys = [k for k in ASSET_REQUIRED_KEYS if k not in asset]
        if missing_asset_keys:
            errors.append(f"{path}.asset: 필수 키 누락 {missing_asset_keys}")

    related = event.get("related_assets")
    if isinstance(related, list):
        for i, ra in enumerate(related):
            if not isinstance(ra, dict) or "symbol" not in ra:
                errors.append(f"{path}.related_assets[{i}]: symbol 없음")
            elif "relation" in ra and ra.get("relation") not in RELATED_ASSET_RELATIONS:
                errors.append(f"{path}.related_assets[{i}].relation: 허용 밖 값 '{ra.get('relation')}'")

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# A2 Step 3: Event Prioritization (2026-08-29/30, A2_Intelligence_Layer_Design.md
# §3-1 PM 확정 4인자 그대로 — Reliability × Novelty × Portfolio Relevance ×
# Magnitude. Importance 인자는 없다(폐기 사유 원문: "event_type별 중요도 사전
# 부여는 관측 사실이 아닌 사전 신념이며, 근거를 추적하면 '예상 주가 영향도'
# (§5.1 금지 입력)로 귀결됨").
# ─────────────────────────────────────────────────────────────────────────────

# Novelty "최근 N일" — 잠정값(§3-1a, news_event_cards.json 158건 이력의
# (종목,event_type) 재등장 간격 분포 조사 근거로 N=7 제안). 아래 두 조건 중
# 하나라도 발생하면 재산출 필요(PM 지시, 2026-08-29 Step 3 체크리스트):
#   1. watchlist.json이 채워져 관심종목 유니버스가 확장될 때(현재는 비어 있어
#      유니버스가 보유종목뿐 — §4-2에서도 같은 제약을 기록함).
#   2. "이상행동" 단일 버킷이 거래량_급증/변동성_급증/가격_갭 3종으로 분해될 때
#      — 사실 기록: 이 분해는 A2 Step 2(2026-08-29, 같은 날)에서 이미
#      일어났다. 이 사실이 지금 즉시 재산출을 요구하는지는 이 코드가 판단하지
#      않는다("상태는 사실대로 적되 판정은 내리지 않는다" 원칙, CLAUDE.md
#      세션 시작 체크리스트) — PM 판단 대상.
NOVELTY_LOOKBACK_DAYS = 7  # 잠정값 - 위 두 조건에서 재산출

# audit_schema()의 첫 실사용 사례(PM 지시). priority_score는 FORBIDDEN_FIELDS_BASE의
# "score"와 정확히 같은 문자열이 아니라 지금 audit_schema()의 정확일치 로직으로는
# 사실 안 걸린다 — 그런데도 경로를 사전 등록해두는 이유는 §3-3에 적은 그대로:
# "우연히 안 걸림"에 기대지 않고 "이 위치는 검토 후 허용됨"을 코드에 남기기
# 위해서다(예: FORBIDDEN_FIELDS_BASE가 나중에 priority_score까지 포함하도록
# 넓어지거나, 다른 모듈이 이 필드를 그냥 "score"로 짓는 걸 막는 안전장치).
PRIORITY_ALLOWED_FIELD_PATHS = frozenset({
    "report.change_events[].priority.priority_score",
})


def _parse_common_timestamp(value):
    """공통 스키마 timestamp(ISO 8601 UTC) 문자열을 datetime으로. 실패하면
    None — Novelty 계산이 파싱 불가 이벤트를 조용히 건너뛰게 한다(§1-1
    timestamp가 검증을 통과했다는 전제가 깨져도 크래시하지 않는다)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def compute_novelty(event, prior_events, lookback_days=NOVELTY_LOOKBACK_DAYS):
    """§3-1: "같은 종목·같은 event_type이 최근 N일 내 이미 발생했는지(있으면
    감쇠, 없으면 1.0)". prior_events 중 이 이벤트와 같은 (symbol, event_type)
    조합이면서 timestamp가 이 이벤트보다 앞선 것들 중 가장 최근 것과의 날짜
    차이를 lookback_days로 나눠 선형 감쇠시킨다(1.0 상한 — N일 이상 지났으면
    "완전히 새로움"과 동일 취급). 같은 조합의 과거 이력이 전혀 없으면 1.0 —
    "정보 없음"을 낮은 신규성으로 잘못 해석하지 않는다(새 이벤트를 부당하게
    낮게 평가하지 않기 위함)."""
    symbol = (event.get("asset") or {}).get("symbol")
    event_type = event.get("event_type")
    event_ts = _parse_common_timestamp(event.get("timestamp"))
    if symbol is None or event_ts is None:
        return 1.0
    prior_ts = []
    for e in prior_events:
        if (e.get("asset") or {}).get("symbol") != symbol or e.get("event_type") != event_type:
            continue
        ts = _parse_common_timestamp(e.get("timestamp"))
        if ts is not None and ts < event_ts:
            prior_ts.append(ts)
    if not prior_ts:
        return 1.0
    days_since = (event_ts - max(prior_ts)).total_seconds() / 86400
    return round(min(1.0, max(0.0, days_since / lookback_days)), 4)


def compute_magnitude(event):
    """§3-1 "계산 제안: change 필드 값 그대로"를 그대로 구현한다 — change의
    절대값을 쓴다(방향은 배제, 크기만). 알려진 한계: event_type마다 change의
    단위가 다르다(거래량_급증은 배율, 가격_갭은 %, 변동성_급증은 백분위) —
    이 셋을 공통 척도로 정규화하는 건 설계 문서가 "또는 abs(change - 1.0)
    등 정규화"로 대안만 남기고 확정하지 않았으므로 이 구현에서 임의로
    선택하지 않는다(A5 이후 필요해지면 재검토)."""
    change = event.get("change")
    return round(abs(change), 4) if change is not None else 0.0


def compute_priority(event, portfolio_relevance, prior_events=None):
    """4인자 Prioritization(§3-1): Reliability × Novelty × Portfolio Relevance
    × Magnitude.

    portfolio_relevance: Step 4(compute_portfolio_relevance, 아직 미구현)가
    만들 값을 그대로 받는다 — 이 함수는 Step 4의 구현 방식을 몰라도 되게
    설계했다(호출자가 relevance_value를 넘겨주기만 하면 됨).
    prior_events: Novelty 계산에 쓸 과거 change_events 로그. 생략하면
    Novelty=1.0으로 계산(과거 이력 없음과 동일하게 취급)."""
    reliability = event.get("reliability", 0.0)
    novelty = compute_novelty(event, prior_events or [])
    magnitude = compute_magnitude(event)
    priority_score = round(reliability * novelty * portfolio_relevance * magnitude, 4)
    return {
        "priority_score": priority_score,
        "factors": {
            "reliability": reliability,
            "novelty": novelty,
            "portfolio_relevance": portfolio_relevance,
            "magnitude": magnitude,
        },
    }


def attach_priorities(report, portfolio_relevance_by_symbol, prior_events=None):
    """report["change_events"] 각 항목에 .priority(위 compute_priority 결과)를
    채운 새 리포트를 반환한다(원본 dict는 바꾸지 않음). audit_schema()로 검사한
    뒤 위반이 있으면 "_audit_violations"에 태그만 남긴다(rule_trigger_report.py
    패턴 — 저장 자체를 막지는 않는다. market_indicators.py처럼 "위반 시 전체
    반려"가 필요한지는 이 함수를 실제로 어디서 호출하는지에 달려 있어 이 A2
    Step 3 자체 범위에서 결정하지 않는다).

    portfolio_relevance_by_symbol: {symbol: relevance_value} — Step 4가 만드는
    맵을 그대로 받는다(이 함수는 Step 4를 호출하지 않는다 - 값만 소비)."""
    prior = list(prior_events or [])
    events_with_priority = []
    for ev in report.get("change_events", []):
        symbol = (ev.get("asset") or {}).get("symbol")
        relevance = portfolio_relevance_by_symbol.get(symbol, 0.0)
        priority = compute_priority(ev, relevance, prior_events=prior)
        new_ev = dict(ev)
        new_ev["priority"] = priority
        events_with_priority.append(new_ev)
    new_report = dict(report)
    new_report["change_events"] = events_with_priority
    violations = audit_schema(new_report, allowed_paths=PRIORITY_ALLOWED_FIELD_PATHS)
    if violations:
        new_report["_audit_violations"] = violations
    return new_report


def calc_ma(prices, window):
    return sum(prices[-window:]) / window

def calc_rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))

def calc_bollinger(prices, window=20, num_std=2):
    ma = calc_ma(prices, window)
    recent = prices[-window:]
    variance = sum((p - ma) ** 2 for p in recent) / window
    std = math.sqrt(variance)
    return ma + num_std * std, ma, ma - num_std * std

def estimate_holding_period(prices):
    if len(prices) < 25:
        return 7
    ma20_series = [calc_ma(prices[:i+1], 20) for i in range(19, len(prices))]
    lengths, cur = [], 1
    for i in range(1, len(ma20_series)):
        up_now = ma20_series[i] > ma20_series[i-1]
        up_prev = ma20_series[i-1] > ma20_series[i-2] if i > 1 else up_now
        if up_now == up_prev:
            cur += 1
        else:
            lengths.append(cur)
            cur = 1
    lengths.append(cur)
    avg = sum(lengths) / len(lengths) if lengths else 7
    return max(3, round(avg))

def is_golden_cross(closes, short=20, long=60):
    """단순이동평균 골든크로스 감지: 직전 봉까지는 short≤long이었다가
    이번 봉에서 short>long으로 상향 돌파했는지."""
    if len(closes) < long + 1:
        return False
    ma_short_now, ma_long_now = calc_ma(closes, short), calc_ma(closes, long)
    ma_short_prev, ma_long_prev = calc_ma(closes[:-1], short), calc_ma(closes[:-1], long)
    return ma_short_prev <= ma_long_prev and ma_short_now > ma_long_now

def calc_adx(highs, lows, closes, period=14):
    """추세 강도 근사치. calc_rsi와 동일하게 최근 period 구간을 단순평균해서
    구하는 간이 버전이며(Wilder 재귀평활은 생략), 25 이상이면 '추세가 있다'는
    게이트로만 쓴다 — 정밀한 ADX 값 자체가 목적이 아님."""
    n = len(closes)
    if n < period + 1:
        return 0
    plus_dms, minus_dms, trs = [], [], []
    for i in range(n - period, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dms.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dms.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    avg_tr = sum(trs) / len(trs)
    if avg_tr == 0:
        return 0
    plus_di = 100 * (sum(plus_dms) / len(plus_dms)) / avg_tr
    minus_di = 100 * (sum(minus_dms) / len(minus_dms)) / avg_tr
    denom = plus_di + minus_di
    if denom == 0:
        return 0
    return 100 * abs(plus_di - minus_di) / denom

def daily_returns(closes):
    return [(closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes)) if closes[i - 1]]


def rolling_volatility_series(closes, window=20):
    """일간수익률의 표준편차를 window 구간씩 굴려가며 계산한 시계열.
    마지막 값이 "오늘의 window일 변동성"이고, 시계열 전체가 백분위를 매길
    과거 분포다.

    2026-08-29 A2 Step 2: market_indicators.py 전용이었던 걸 여기로 옮겼다 —
    news_event_cards.py의 detect_anomalies()도 같은 방식(백분위)으로 변동성
    급증을 판정하도록 통일하면서(PM 지시, A2_Intelligence_Layer_Design.md
    §2-3) 두 파일이 같은 계산식을 import해서 쓰게 하기 위해서다. 함수를
    복붙하면 나중에 계산식이 갈라질 수 있어(FORBIDDEN_FIELDS_BASE가 겪었던
    종류의 드리프트) 공유 모듈로 옮기는 쪽을 택했다."""
    rets = daily_returns(closes)
    series = []
    for i in range(window, len(rets) + 1):
        chunk = rets[i - window:i]
        mean = sum(chunk) / len(chunk)
        var = sum((r - mean) ** 2 for r in chunk) / len(chunk)
        series.append(var ** 0.5)
    return series


def historical_percentile(series):
    """series의 마지막 값이 series 전체 분포에서 몇 번째 백분위인지.
    "지금 값 / 과거 분포에서의 위치"만 반환 — 라벨을 붙이지 않는다."""
    if not series:
        return None
    current = series[-1]
    rank = sum(1 for v in series if v <= current)
    return round(100 * rank / len(series), 1)


def classify_strategy(expected_days):
    if expected_days <= 6:
        return "단타"
    elif expected_days <= 20:
        return "스윙"
    return "장기"

def entry_score(closes, volumes=None):
    """스캔/백테스트가 공유하는 관심종목 사전 필터. 라이브 스캔과 과거 시뮬레이션이
    서로 다른 로직으로 갈라지지 않도록 여기서 한 곳에만 둔다.

    Phase 2부터는 이 점수가 매수 근거가 아니다 — 하루에 전체 마켓(크립토만 80개+)을
    다 Claude에 보낼 수 없어서 후보를 추리는 실무적 사전 필터일 뿐이고, 실제 매수/매도
    판단은 ask_claude_decision이 뉴스 사건을 중심으로 내린다(계획서 v3 원칙 #4).
    HARD_STOP_LOSS만 여전히 AI 판단과 무관한 무조건 안전장치다."""
    rsi = calc_rsi(closes)
    upper, mid, lower = calc_bollinger(closes)
    price = closes[-1]
    score = 0
    if 30 <= rsi <= 45:
        score += 2
    if price <= lower * 1.03:
        score += 2
    if volumes is not None:
        avg_vol = sum(volumes[-5:]) / 5
        if volumes[-1] > avg_vol * 1.3:
            score += 1
    return score, rsi


def get_krw_candles(market, count=60):
    """일봉 조회. count<=200이면 단일 호출(기존 동작과 동일),
    그보다 크면 `to` 파라미터로 과거 방향 페이지네이션한다(백테스트의 장기 히스토리 조회용)."""
    all_candles = []
    to_param = None
    while len(all_candles) < count:
        batch_size = min(200, count - len(all_candles))
        params = {"market": market, "count": batch_size}
        if to_param:
            params["to"] = to_param
        batch = requests.get("https://api.upbit.com/v1/candles/days", params=params, timeout=10).json()
        if not batch:
            break
        all_candles.extend(batch)
        to_param = batch[-1]["candle_date_time_utc"]
        if len(batch) < batch_size:
            break
        if len(all_candles) < count:
            time.sleep(0.12)  # 업비트 rate limit 배려 - 다중 페이지네이션(백테스트의 대량 히스토리 조회)에서만 발생
    all_candles.reverse()
    return all_candles

def get_all_krw_markets():
    data = requests.get("https://api.upbit.com/v1/market/all", timeout=10).json()
    return [m['market'] for m in data if m['market'].startswith("KRW-") and m['market'] not in EXCLUDE_MARKETS]

def get_krw_price(market):
    data = requests.get("https://api.upbit.com/v1/ticker", params={"markets": market}, timeout=10).json()
    return data[0]['trade_price']

def scan_crypto(exclude, top_n=3):
    results = []
    for market in get_all_krw_markets()[:80]:
        if market in exclude:
            continue
        try:
            candles = get_krw_candles(market, 30)
            closes = [c['trade_price'] for c in candles]
            volumes = [c['candle_acc_trade_volume'] for c in candles]
            if len(closes) < 20:
                continue
            score, rsi = entry_score(closes, volumes)
            price = closes[-1]
            if score >= 3:
                results.append({"market": market, "asset_class": "crypto", "score": score, "rsi": rsi, "price": price, "raw_closes": closes})
        except Exception:
            continue
    results.sort(key=lambda x: -x["score"])
    return results[:top_n]


HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; quantrade-bot/1.0)"}


def get_us_closes(ticker, count=60):
    """미국주식 일봉 종가. stooq가 GitHub Actions IP에서 봇차단 JS 챌린지를 주는 것이
    확인되어(phase-1 백테스트, backtest_report.json에 미국주식 결과가 아예 안 잡힘 —
    CLAUDE.md 참고) Yahoo Finance 차트 API를 우선 시도하고, 실패하면 stooq로 폴백한다.
    Yahoo도 언젠가 같은 이유로 막힐 수 있고 이 환경에서는 실제 네트워크 검증이
    불가능했으므로, daily.yml/backtest.yml 실행 로그로 실제 동작을 확인할 것."""
    errors = []
    try:
        return _get_us_closes_yahoo(ticker, count)
    except Exception as e:
        errors.append(f"yahoo: {e}")
    try:
        return _get_us_closes_stooq(ticker, count)
    except Exception as e:
        errors.append(f"stooq: {e}")
    raise ValueError(f"{ticker} 시세 조회 실패 - " + " / ".join(errors))


def _get_us_closes_yahoo(ticker, count):
    end = datetime.now()
    start = end - timedelta(days=int(count * 1.6) + 30)
    params = {"period1": int(start.timestamp()), "period2": int(end.timestamp()), "interval": "1d"}
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}",
        params=params, timeout=10, headers=HTTP_HEADERS,
    )
    try:
        data = resp.json()
    except ValueError:
        raise ValueError(f"JSON 아님 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    result = (data.get("chart") or {}).get("result")
    if not result:
        err = (data.get("chart") or {}).get("error")
        raise ValueError(f"result 없음 (error={err}, status={resp.status_code})")
    closes_raw = result[0]["indicators"]["quote"][0]["close"]
    closes = [c for c in closes_raw if c is not None]
    if not closes:
        raise ValueError("유효한 종가 없음")
    return closes[-count:]


def _get_us_closes_stooq(ticker, count):
    resp = requests.get(f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d", timeout=10, headers=HTTP_HEADERS)
    lines = resp.text.strip().split("\n")
    if not lines or not lines[0].lower().startswith("date,"):
        raise ValueError(
            f"CSV 대신 다른 응답 - 클라우드 IP 차단(봇 감지) 가능성 "
            f"(status={resp.status_code}, body[:120]={resp.text[:120]!r})"
        )
    closes = [float(l.split(",")[4]) for l in lines[1:] if len(l.split(",")) >= 5]
    if not closes:
        raise ValueError(f"stooq 응답에서 시세를 못 찾음 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    return closes[-count:]

def get_us_price(ticker):
    return get_us_closes(ticker, 5)[-1]

def get_us_candles(ticker, count=60):
    """get_us_closes와 별개로 OHLC 전체가 필요한 소비자(백테스트의 ADX 계산 등)용.
    라이브 스캔(scan_stocks/get_us_price)은 계속 get_us_closes만 쓰므로 영향 없음.
    get_us_closes와 동일하게 Yahoo 우선, stooq 폴백 순서를 따른다."""
    errors = []
    try:
        return _get_us_candles_yahoo(ticker, count)
    except Exception as e:
        errors.append(f"yahoo: {e}")
    try:
        return _get_us_candles_stooq(ticker, count)
    except Exception as e:
        errors.append(f"stooq: {e}")
    raise ValueError(f"{ticker} OHLC 조회 실패 - " + " / ".join(errors))


def _get_us_candles_yahoo(ticker, count):
    end = datetime.now()
    start = end - timedelta(days=int(count * 1.6) + 30)
    params = {"period1": int(start.timestamp()), "period2": int(end.timestamp()), "interval": "1d"}
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}",
        params=params, timeout=10, headers=HTTP_HEADERS,
    )
    try:
        data = resp.json()
    except ValueError:
        raise ValueError(f"JSON 아님 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    result = (data.get("chart") or {}).get("result")
    if not result:
        err = (data.get("chart") or {}).get("error")
        raise ValueError(f"result 없음 (error={err}, status={resp.status_code})")
    timestamps = result[0].get("timestamp") or []
    quote = result[0]["indicators"]["quote"][0]
    candles = []
    for i, ts in enumerate(timestamps):
        o, h, l, c = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i]
        if None in (o, h, l, c):
            continue
        candles.append({
            "date": datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
            "open": o, "high": h, "low": l, "close": c, "volume": quote["volume"][i] or 0,
        })
    if not candles:
        raise ValueError("유효한 OHLC 없음")
    return candles[-count:]


def _get_us_candles_stooq(ticker, count):
    resp = requests.get(f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d", timeout=10, headers=HTTP_HEADERS)
    lines = resp.text.strip().split("\n")
    if not lines or not lines[0].lower().startswith("date,"):
        raise ValueError(
            f"CSV 대신 다른 응답 - 클라우드 IP 차단(봇 감지) 가능성 "
            f"(status={resp.status_code}, body[:120]={resp.text[:120]!r})"
        )
    candles = []
    for l in lines[1:]:
        parts = l.split(",")
        if len(parts) < 6:
            continue
        candles.append({"date": parts[0], "open": float(parts[1]), "high": float(parts[2]),
                         "low": float(parts[3]), "close": float(parts[4]), "volume": float(parts[5])})
    if not candles:
        raise ValueError(f"stooq 응답에서 시세를 못 찾음 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    return candles[-count:]

def scan_stocks(exclude, top_n=2):
    results = []
    for ticker in US_STOCKS:
        if ticker in exclude:
            continue
        try:
            closes = get_us_closes(ticker, 30)
            if len(closes) < 20:
                continue
            score, rsi = entry_score(closes)
            price = closes[-1]
            if score >= 2:
                results.append({"market": ticker, "asset_class": "stock", "score": score, "rsi": rsi, "price": price, "raw_closes": closes})
        except Exception:
            continue
    results.sort(key=lambda x: -x["score"])
    return results[:top_n]


def get_krx_price(code):
    url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
    data = requests.get(url, timeout=10).json()
    return float(data["datas"][0]["closePrice"].replace(",", ""))

def get_krx_candles(code, count=750):
    """국내 주식 일봉 히스토리. 토스증권 API 연동 전까지는 네이버 금융 시세를
    과거 데이터 소스로 사용한다(계획서 v3 §3.2). 응답이 순수 JSON이 아닌
    JS 배열 리터럴이라 정규식으로 행만 추출한다."""
    end = datetime.now()
    start = end - timedelta(days=int(count * 1.6) + 30)  # 주말/휴장일 감안한 여유
    params = {
        "symbol": code, "requestType": 1,
        "startTime": start.strftime("%Y%m%d"), "endTime": end.strftime("%Y%m%d"),
        "timeframe": "day",
    }
    resp = requests.get("https://api.finance.naver.com/siseJson.naver", params=params, timeout=10, headers=HTTP_HEADERS)
    rows = re.findall(
        r"\[[\"'](\d{8})[\"'],\s*([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+)",
        resp.text,
    )
    if not rows:
        raise ValueError(f"네이버 시세 응답에서 데이터를 못 찾음 (status={resp.status_code}, body[:120]={resp.text[:120]!r})")
    candles = [
        # r[0]은 "20211207" 형태(구분자 없는 8자리) — 크립토/미국주식 캔들의
        # "date" 필드는 전부 "YYYY-MM-DD"라 여기도 대시를 넣어 형식을 통일한다.
        # 2026-08-01: backtest.py의 compute_portfolio_mdd()가 entry_date/exit_date를
        # strptime("%Y-%m-%d")로 파싱하다가 이 불일치로 실제로 크래시났다(KRX 거래에서만).
        {"date": f"{r[0][:4]}-{r[0][4:6]}-{r[0][6:8]}", "open": float(r[1]), "high": float(r[2]),
         "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])}
        for r in rows
    ]
    return candles[-count:]


def get_news_sentiment(query):
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        titles = [item.find("title").text for item in root.findall(".//item")][:10]
    except Exception:
        return "뉴스 조회 실패"
    pos = sum(1 for t in titles for w in POSITIVE_WORDS if w in t.lower())
    neg = sum(1 for t in titles for w in NEGATIVE_WORDS if w in t.lower())
    if pos + neg == 0:
        return "중립"
    if pos > neg:
        return f"긍정 우세 ({pos}/{neg})"
    if neg > pos:
        return f"부정 우세 ({pos}/{neg})"
    return "혼조"


def get_news_headlines(query, limit=5):
    """[실험 단계 전용 — ask_claude_decision/analyze.py의 실제 승인 흐름에는
    연결돼 있지 않다] 뉴스 헤드라인 원문을 가져온다 — 사건 추출용(계획서 v3
    원칙 #4: "뉴스는 감성이 아니라 사건 단위로 분석해야 의미가 있다").

    2026-08-01: get_news_sentiment를 대체해 ask_claude_decision에 직접
    연결했었으나, 검증되지 않은 변경을 실제 승인 흐름에 바로 반영한 것 자체가
    "안전장치·승인기준은 검증 전 변경 금지" 원칙 위반이라 되돌렸다. 이 함수와
    _format_news는 삭제하지 않고 별도 실험 스크립트(news_event_experiment.py)
    전용으로 남겨둔다 — 캘리브레이션 결과가 나온 뒤에 언제/어떻게 실제 흐름에
    다시 연결할지 별도로 논의한다. 그 전까지 라이브 뉴스 판단은
    get_news_sentiment(감성 단어 카운트)가 담당한다.

    2026-08-01 추가 변경: Phase 2가 KRX 중심(계획서 원칙)이라 쿼리 로케일을
    en-US에서 ko-KR로 바꿨다 — 실적발표/공시/M&A/규제 같은 사건 뉴스는 거의
    다 한국어로 나오므로 영어 로케일로는 관련 기사를 거의 못 찾는다.
    get_news_sentiment는 여전히 라이브 경로라 로케일을 그대로 두고 건드리지
    않았다(분리 원칙). query는 종목코드(예: "005930") 그대로 넘기면 되는데,
    한국 금융 기사는 관례적으로 회사명 옆에 "(코드)"를 병기하는 경우가 많아
    코드만으로도 어느 정도 매칭이 되지만, 회사명 매핑이 없어 코드만 못 실린
    기사는 놓친다 — 재현율을 더 높이려면 종목코드→회사명 매핑이 필요하고,
    이건 이 세션 스코프 밖으로 남겨둔다(Naver 실시간시세 API가 이름 필드를
    주는지는 이 샌드박스에서 네트워크가 막혀 있어 확인하지 못했다).

    반환값: 성공 시 헤드라인 리스트(빈 리스트=진짜 관련 뉴스 없음), 조회 자체가
    실패하면 None(네트워크 실패와 "뉴스 없음"을 구분해야 프롬프트에서 다르게
    표현할 수 있다)."""
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        titles = [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
        return titles[:limit]
    except Exception:
        return None


def load_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            return default
    return default

def save_json(path, data):
    json.dump(data, open(path, "w"), indent=2, ensure_ascii=False)

def get_current_price(asset_class, market):
    if asset_class == "crypto":
        return get_krw_price(market)
    elif asset_class == "krx":
        return get_krx_price(market)
    else:
        return get_us_price(market)


def _format_news(headlines):
    """[실험 단계 전용] get_news_headlines의 출력(헤드라인 리스트/None/빈 리스트)을
    사람이 읽을 문자열로 바꾸는 포맷터. get_news_headlines와 마찬가지로 현재
    ask_claude_decision에서는 쓰지 않는다 — 짝을 이루는 함수라 같이 남겨둔다."""
    if headlines is None:
        return "뉴스 조회 실패"
    if not headlines:
        return "관련 뉴스 없음"
    return " / ".join(headlines)


def ask_claude_decision(held_positions, candidates, news_by_market, real_positions=None):
    real_positions = real_positions or []
    tradeable = [p for p in held_positions if not p.get("conviction")]
    conviction_holds = [p for p in held_positions if p.get("conviction")]

    holdings_text = "\n".join([
        f"- {p['market']} ({p.get('strategy_type','스윙')}): 진입가 {p['entry_price']}, 현재 {p.get('current_price','?')}, 수익률 {p.get('current_return', 0):+.2f}%"
        for p in tradeable
    ]) or "없음"

    conviction_text = "\n".join([
        f"- {p['market']}: 수익률 {p.get('current_return', 0):+.2f}% (사용자 확신 장기보유, 매도 판단 대상 아님)"
        for p in conviction_holds
    ]) or "없음"

    candidates_text = "\n".join([
        f"- {c['market']} ({c['asset_class']}): 점수 {c['score']}, RSI {c['rsi']:.0f}, 예상보유 {c['expected_days']}일, 뉴스분위기 {news_by_market.get(c['market'], '정보없음')}"
        for c in candidates
    ]) or "없음"

    # 실계좌(토스) 보유종목 — 계좌번호 등 식별정보는 절대 넘기지 않는다. 종목명/수량/현재가/
    # 수익률만 전달(analyze.py에서 이미 필터링해서 넘어옴).
    real_text = "\n".join([
        f"- {p['name']} ({p['symbol']}): 수량 {p['quantity']}, 현재가 {p['current_price']}, 수익률 {p.get('return_pct', 0):+.2f}%"
        for p in real_positions
    ]) or "없음"

    prompt_text = (
        "너는 개인 투자자를 위한 퀀트 자산관리 AI야. 아래 정보를 보고 실제 결정을 내려줘.\n\n"
        f"[매매 판단 대상 보유 포지션]\n{holdings_text}\n\n"
        f"[사용자 확신 장기보유 종목 - 참고만]\n{conviction_text}\n\n"
        f"[신규 진입 후보]\n{candidates_text}\n\n"
        f"[실계좌 보유종목 - 조회전용, 매도 또는 비중조정만 판단(매수 불가)]\n{real_text}\n\n"
        "실계좌 종목에 대한 결정은 market 필드를 반드시 'REAL:종목코드' 형식으로 써(예: REAL:005930). "
        "action은 매도 또는 비중조정만 가능하고, 보유가 적절한 실계좌 종목은 별도 decision을 만들지 마.\n\n"
        "다음 JSON 형식으로만 답해줘. 매우 중요한 규칙:\n"
        "- 다른 설명 텍스트 없이 순수 JSON만 출력\n"
        "- 모든 문자열 값은 반드시 큰따옴표로 감싸고, 문자열 안에는 줄바꿈이나 큰따옴표를 절대 넣지 마\n"
        "- reasoning은 한 줄로, 쉼표나 마침표로만 문장을 구분해\n\n"
        "{\n"
        '  "market_summary": "전체 시장 상황 한 줄 요약",\n'
        '  "decisions": [\n'
        "    {\n"
        '      "market": "종목코드",\n'
        '      "action": "매도 또는 매수 또는 보유 또는 비중조정",\n'
        '      "target_weight_pct": 0에서100사이숫자 또는 null,\n'
        '      "reasoning": "한 줄로 된 이유"\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    for attempt in range(2):  # 실패하면 한 번 더 시도
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-6", "max_tokens": 1500, "messages": [{"role": "user", "content": prompt_text}]},
                timeout=30
            )
            data = response.json()
            if "content" not in data:
                return {"market_summary": f"AI 응답 오류: {data}", "decisions": []}
            raw_text = data["content"][0]["text"]
            cleaned = raw_text.strip().replace("```json", "").replace("```", "").strip()
            # 혹시 앞뒤에 다른 텍스트가 섞였으면 { } 부분만 추출
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
            return json.loads(cleaned)
        except Exception as e:
            if attempt == 0:
                continue  # 한 번 더 시도
            return {"market_summary": f"AI 판단 실패: {e}", "decisions": []}
    return {"market_summary": "AI 판단 실패: 재시도 초과", "decisions": []}


def send_telegram(msg):
    if not msg:
        msg = "(빈 메시지)"
    for i in range(0, len(msg), 4000):
        try:
            resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                  data={"chat_id": TELEGRAM_CHAT_ID, "text": msg[i:i+4000]}, timeout=15)
            print("텔레그램 응답:", resp.json())
        except Exception as e:
            print("⚠️ 텔레그램 실패:", e)


def run_self_test():
    """analyze_lib.py 자체 검증 (네트워크 미사용). A2 Step 1 착수(2026-08-29)
    시점에는 공통 이벤트 스키마만 검증한다 — 이 파일의 나머지 함수(지표 계산,
    시세 조회 등)는 각자를 쓰는 다른 파일의 self-test/실행으로 이미 간접
    검증되고 있고, 여기 새로 추가할 이유가 없다."""
    print("=== analyze_lib.py 자체 검증 (공통 이벤트 스키마, 네트워크 미사용) ===\n")

    sample_asset = {"symbol": "005930", "name": "삼성전자", "market_country": "KR", "currency": "KRW"}

    # 1) 정상 이벤트 - 산술 기반(거래량 급증), 관측치 있음
    ev = build_common_event(
        timestamp="2026-08-29T07:13:48+00:00",
        asset=sample_asset,
        source="news_event_cards.anomaly",
        event_type="거래량_급증",
        reliability=1.0,
        observed_value=1234567.0,
        baseline=500000.0,
        change=2.47,
    )
    print(f"[1] 정상 이벤트(산술) 생성 성공: {sorted(ev)}")
    assert set(ev) == set(COMMON_EVENT_SCHEMA), "9개 필드 집합이 스키마와 다름"
    assert validate_common_event(ev) == [], f"정상 이벤트인데 위반 발생: {validate_common_event(ev)}"

    # 2) 정상 이벤트 - 뉴스처럼 수치가 없는 경우(observed_value/baseline/change 전부 None 허용).
    #    event_type 자체의 의미론적 적절성은 이 테스트의 관심사가 아니다 - 스키마는
    #    "이 event_type이면 수치가 꼭 있어야 한다"는 제약을 강제하지 않는다(§1-1
    #    "조건부 필수"는 생성기 쪽 책임이지 스키마 검증기가 event_type별로 분기하는
    #    규칙이 아니다).
    ev_news = build_common_event(
        timestamp="2026-08-29T07:13:48+00:00",
        asset=sample_asset,
        source="news_event_cards.ai_summary",
        event_type="상관관계_변화",
        reliability=0.8,
    )
    print(f"[2] 수치 없는 이벤트(뉴스형) 생성 성공: observed_value={ev_news['observed_value']}")
    assert ev_news["observed_value"] is None and ev_news["baseline"] is None and ev_news["change"] is None

    # 3) 필수 필드 누락 -> ValueError (asset 누락)
    try:
        build_common_event(timestamp="2026-08-29T07:13:48+00:00", asset=None,
                            source="x", event_type="거래량_급증", reliability=1.0)
        raised = False
    except ValueError:
        raised = True
    print(f"[3] asset 누락 -> ValueError 발생={raised}")
    assert raised, "필수 필드(asset) 누락인데 ValueError가 안 남"

    # 4) event_type이 허용 밖 값이면 ValueError (v3.2 금지 예측 필드 유사 방식 - 사전 등록되지 않은 값 거부)
    try:
        build_common_event(timestamp="2026-08-29T07:13:48+00:00", asset=sample_asset,
                            source="x", event_type="호재판단", reliability=1.0)
        raised = False
    except ValueError:
        raised = True
    print(f"[4] 허용 밖 event_type -> ValueError 발생={raised}")
    assert raised, "허용 밖 event_type인데 ValueError가 안 남"

    # 5) reliability 범위 밖(0~1) -> ValueError
    try:
        build_common_event(timestamp="2026-08-29T07:13:48+00:00", asset=sample_asset,
                            source="x", event_type="거래량_급증", reliability=1.5)
        raised = False
    except ValueError:
        raised = True
    print(f"[5] reliability=1.5(범위 밖) -> ValueError 발생={raised}")
    assert raised, "reliability 범위 위반인데 ValueError가 안 남"

    # 6) timestamp가 오프셋 없는 naive 문자열이면 위반 - rule_trigger_report.py가
    #    실제로 겪었던 문제(KST naive)가 스키마 검증에서 조용히 통과하면 안 된다.
    naive_errors = validate_common_event({**ev, "timestamp": "2026-08-29 16:13"})
    print(f"[6] naive timestamp -> 위반 {naive_errors}")
    assert any("timestamp" in e for e in naive_errors), "오프셋 없는 timestamp를 못 잡음"

    # 7) related_assets: relation이 허용 enum 밖이면 위반
    bad_related = {**ev, "related_assets": [{"symbol": "000660", "relation": "임의값"}]}
    rel_errors = validate_common_event(bad_related)
    print(f"[7] related_assets.relation 허용 밖 값 -> 위반 {rel_errors}")
    assert any("relation" in e for e in rel_errors), "허용 밖 relation 값을 못 잡음"

    # 8) related_assets: 정상 relation 값이면 위반 없음
    good_related = {**ev, "related_assets": [{"symbol": "000660", "name": "SK하이닉스",
                                              "relation": "correlation_pair"}]}
    print(f"[8] 정상 related_assets -> 위반 {validate_common_event(good_related)}")
    assert validate_common_event(good_related) == []

    # 9) EVENT_TYPE_ENUM = ACTIVE 4종 + RESERVED 2종, 서로 겹치지 않음(§2-3)
    print(f"[9] ACTIVE={EVENT_TYPE_ACTIVE}, RESERVED={EVENT_TYPE_RESERVED}")
    assert len(EVENT_TYPE_ACTIVE) == 4 and len(EVENT_TYPE_RESERVED) == 2
    assert set(EVENT_TYPE_ACTIVE).isdisjoint(EVENT_TYPE_RESERVED)
    assert EVENT_TYPE_ENUM == EVENT_TYPE_ACTIVE + EVENT_TYPE_RESERVED

    # 10) COMMON_EVENT_SOURCES가 §1-2 매핑표의 5개 생성기를 전부 커버하는지
    covered_modules = {src.split(".")[0] for src in COMMON_EVENT_SOURCES}
    expected_modules = {"news_event_cards", "market_indicators", "portfolio_report",
                         "post_trade_review", "rule_trigger_report"}
    print(f"[10] source 레지스트리가 커버하는 모듈: {sorted(covered_modules)}")
    assert covered_modules == expected_modules, f"5개 생성기 매핑 누락: {expected_modules - covered_modules}"

    # 11) asset에 필수 키가 빠지면 위반(예: currency 없음)
    incomplete_asset = {**ev, "asset": {"symbol": "005930", "name": "삼성전자", "market_country": "KR"}}
    asset_errors = validate_common_event(incomplete_asset)
    print(f"[11] currency 없는 asset -> 위반 {asset_errors}")
    assert any("asset" in e for e in asset_errors), "asset 필수 키 누락을 못 잡음"

    # ── A2 Step 2.5: audit_schema() 경로단위 allowlist (§3-3) ──────────────

    # 12) normalize_path — 배열 인덱스를 지워 패턴으로 만드는지
    p1 = normalize_path("report.change_events[3].priority.priority_score")
    p2 = normalize_path("report.change_events[0].priority.priority_score")
    print(f"[12] normalize_path: idx=3 -> {p1!r}, idx=0 -> {p2!r}")
    assert p1 == p2 == "report.change_events[].priority.priority_score"

    # 13) audit_schema — 등록 안 된 경로에서 금지 필드(정확히 "score")가 나오면 걸리는지
    dirty_report = {"change_events": [{"priority": {"score": 0.5}}]}
    violations_unregistered = audit_schema(dirty_report)
    print(f"[13] 미등록 경로의 'score' 필드 -> 위반 {violations_unregistered}")
    assert any("score" in v for v in violations_unregistered), "미등록 경로의 금지 필드를 못 잡음"

    # 14) 같은 구조라도 정확히 그 경로가 allowed_paths에 등록되면 위반 없음
    same_path = normalize_path("report.change_events[0].priority.score")
    violations_registered = audit_schema(dirty_report, allowed_paths=frozenset({same_path}))
    print(f"[14] 같은 경로를 allowlist에 등록 -> 위반 {violations_registered}")
    assert violations_registered == [], "등록된 경로인데도 위반으로 잡힘"

    # 15) 등록된 경로 밖의 다른 위치에 같은 금지 필드가 새로 나타나면 여전히 걸리는지
    #     (§3-3 "다른 위치에 우연히 score가 다시 나타나면 여전히 걸린다")
    leaked = {"change_events": [{"priority": {"score": 0.5}}], "other_block": {"score": 99}}
    violations_leak = audit_schema(leaked, allowed_paths=frozenset({same_path}))
    print(f"[15] 등록 경로 외 다른 위치의 'score' -> 위반 {violations_leak}")
    assert any("other_block.score" in v for v in violations_leak), "등록 경로 밖의 금지 필드 누출을 못 잡음"
    assert not any("change_events[0].priority.score" in v for v in violations_leak), \
        "등록된 경로까지 다시 걸리면 안 됨"

    # ── A2 Step 3: Event Prioritization (4인자, §3-1) ──────────────────────

    base_asset = {"symbol": "005930", "name": "삼성전자", "market_country": "KR", "currency": "KRW"}
    ev_today = build_common_event(
        timestamp="2026-08-29T00:00:00+00:00", asset=base_asset,
        source="news_event_cards.anomaly", event_type="거래량_급증",
        reliability=1.0, observed_value=5000, baseline=1000, change=5.0,
    )

    # 16) Novelty — 과거 이력이 전혀 없으면 1.0
    print(f"[16] 과거 이력 없음 -> Novelty={compute_novelty(ev_today, [])}")
    assert compute_novelty(ev_today, []) == 1.0

    # 17) Novelty — 바로 전날 같은 (symbol, event_type) 이벤트가 있으면 강하게 감쇠
    ev_yesterday = {**ev_today, "timestamp": "2026-08-28T00:00:00+00:00"}
    n_1day = compute_novelty(ev_today, [ev_yesterday])
    print(f"[17] 1일 전 같은 조합 재등장 -> Novelty={n_1day} (lookback={NOVELTY_LOOKBACK_DAYS}일)")
    assert n_1day == round(1 / NOVELTY_LOOKBACK_DAYS, 4)

    # 18) Novelty — lookback_days 이상 지났으면 1.0으로 상한(완전히 새로움과 동일 취급)
    ev_long_ago = {**ev_today, "timestamp": "2026-08-01T00:00:00+00:00"}
    n_far = compute_novelty(ev_today, [ev_long_ago])
    print(f"[18] {NOVELTY_LOOKBACK_DAYS}일보다 훨씬 전 재등장 -> Novelty={n_far}")
    assert n_far == 1.0

    # 19) Novelty — 종목이나 event_type이 다르면 이력으로 안 침(무관한 이력 무시)
    ev_other_symbol = {**ev_yesterday, "asset": {**base_asset, "symbol": "000660"}}
    ev_other_type = {**ev_yesterday, "event_type": "가격_갭"}
    n_unrelated = compute_novelty(ev_today, [ev_other_symbol, ev_other_type])
    print(f"[19] 다른 종목/다른 event_type 이력만 있음 -> Novelty={n_unrelated}")
    assert n_unrelated == 1.0, "무관한 이력이 Novelty에 영향을 주면 안 됨"

    # 20) Magnitude — change의 절대값(방향 배제)
    ev_negative_change = {**ev_today, "change": -5.0}
    print(f"[20] change=-5.0 -> Magnitude={compute_magnitude(ev_negative_change)}")
    assert compute_magnitude(ev_negative_change) == 5.0
    assert compute_magnitude({**ev_today, "change": None}) == 0.0

    # 21) compute_priority — 4개 인자의 단순 곱인지 수기 검증
    result = compute_priority(ev_today, portfolio_relevance=0.5, prior_events=[])
    expected = round(1.0 * 1.0 * 0.5 * 5.0, 4)  # reliability=1.0, novelty=1.0(이력없음), relevance=0.5, magnitude=5.0
    print(f"[21] priority_score={result['priority_score']} (기대값 {expected})")
    assert result["priority_score"] == expected
    assert set(result["factors"]) == {"reliability", "novelty", "portfolio_relevance", "magnitude"}

    # 22) attach_priorities — change_events 각각에 .priority가 붙고, 원본은 안 바뀌고,
    #     audit_schema()로 검사해도(§3-3 allowlist 적용) 위반이 없는지
    sample_report = {"generated_at": "2026-08-29T00:00:00+00:00",
                      "schema": "explanation_only_v3.2", "cards": [],
                      "change_events": [ev_today, {**ev_today, "asset": {**base_asset, "symbol": "000660"}}]}
    prioritized = attach_priorities(sample_report, {"005930": 0.8, "000660": 0.2})
    print(f"[22] 원본 change_events에 priority 키 있음={'priority' in sample_report['change_events'][0]}, "
          f"결과 첫 이벤트 priority_score={prioritized['change_events'][0]['priority']['priority_score']}")
    assert "priority" not in sample_report["change_events"][0], "원본 리포트를 변경하면 안 됨"
    assert all("priority" in e for e in prioritized["change_events"])
    assert "_audit_violations" not in prioritized, f"정상 결과인데 감사 위반 태그가 붙음: {prioritized.get('_audit_violations')}"
    assert prioritized["change_events"][0]["priority"]["factors"]["portfolio_relevance"] == 0.8
    assert prioritized["change_events"][1]["priority"]["factors"]["portfolio_relevance"] == 0.2

    # 23) attach_priorities 결과가 실제로 PRIORITY_ALLOWED_FIELD_PATHS와 정합적인지
    #     — 등록된 경로 문자열이 attach_priorities가 실제로 만드는 경로와 같은 패턴인지
    actual_path = normalize_path(f"report.change_events[0].priority.priority_score")
    print(f"[23] 등록된 경로={sorted(PRIORITY_ALLOWED_FIELD_PATHS)}, 실제 생성 경로 패턴={actual_path}")
    assert actual_path in PRIORITY_ALLOWED_FIELD_PATHS

    print("\n모든 자체 검증 통과.")


def main():
    p = argparse.ArgumentParser(description="analyze_lib 공유 로직 자체 검증")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        run_self_test()


if __name__ == "__main__":
    main()

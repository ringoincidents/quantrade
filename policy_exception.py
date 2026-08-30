"""정책 이탈 예외 승인 기록 (A6, 2026-08-30).

portfolio_report.py의 role_gap이 계산한 "역할 배분 목표 초과" 사실에 대해,
사용자가 텔레그램에서 그 이탈을 알고도 예외로 승인했다는 사실만 기록하는
불변 저널이다. post_trade_review_log.json과 같은 append-only 패턴을 그대로
쓴다 — 새 매매 판단이나 추천이 아니라 사용자가 이미 내린 결정을 기록할
뿐이다. gap_pct/target_pct/actual_pct는 이미 role_gap이 계산한 값을 그대로
옮길 뿐 여기서 다시 계산하지 않는다.

[Core, v3.2 활성 기능] — 계산/기록 전용, 예측 없음. 로그 항목을 지우거나
고치는 코드는 만들지 않는다(불변 저널 원칙, post_trade_review.py와 동일).
"""

from datetime import datetime, timezone
from analyze_lib import FORBIDDEN_FIELDS_BASE, FORBIDDEN_PHRASES_BASE, load_json, save_json

LOG_FILE = "policy_exception_log.json"

FORBIDDEN_FIELDS = FORBIDDEN_FIELDS_BASE
FORBIDDEN_PHRASES = FORBIDDEN_PHRASES_BASE


class AuditViolation(Exception):
    """예외 승인 기록이 감사(금지 필드/문구)를 통과하지 못했을 때 던진다.

    post_trade_review.py의 _append_and_save는 감사 위반 시 SystemExit을
    던지지만, 그 파일은 자기 자신이 최상위 진입점(cron 단위 실행)이라
    프로세스가 죽어도 안전하다. 이 모듈은 check_updates.py의 텔레그램 폴링
    루프 안에서 메시지 하나당 한 번씩 호출되므로 SystemExit을 쓰면 안 된다
    — run()의 offset 저장(save_json(OFFSET_FILE, ...))이 루프 밖 맨 끝에
    있어서, 도중에 프로세스가 죽으면 offset이 갱신되지 않고 같은 메시지가
    다음 폴링에서 무한 재처리된다. 그래서 여기는 일반 예외를 던지고,
    호출자(check_updates.handle_approve_exception)가 그 메시지 처리만
    실패시키고 텔레그램으로 사유를 알린 뒤 다음 메시지로 넘어가게 한다."""

    def __init__(self, violations):
        self.violations = violations
        super().__init__("; ".join(violations))


def audit(obj, path="record"):
    """post_trade_review.py/portfolio_report.py와 같은 재귀 감사 패턴 —
    금지 필드/문구가 섞였는지 검사한다."""
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in FORBIDDEN_FIELDS:
                bad.append(f"{path}.{k} (금지 필드)")
            bad += audit(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += audit(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        for ph in FORBIDDEN_PHRASES:
            if ph in obj:
                bad.append(f"{path}: 금지 문구 '{ph}'")
    return bad


def build_record(role_row, reason, approved_by, now=None):
    """role_gap의 한 행(portfolio_report.compute_role_gap 출력)과 사용자 입력
    사유로 예외 승인 레코드를 만든다.

    role_row: {"role", "label", "target_pct", "actual_pct", "gap_pct", ...}
    reason: 사용자가 텔레그램 명령에 함께 적은 자유서술 사유(또는 사전에
        합의한 카테고리 단어를 그대로 적어도 됨 — 이 파일이 카테고리를
        따로 강제하지 않는다).
    approved_by: 텔레그램 발신자 식별 문자열(check_updates.py가
        message["from"]에서 만들어 넘긴다) — 이 모듈은 Telegram API를
        직접 건드리지 않는다."""
    now = now or datetime.now(timezone.utc).isoformat()
    return {
        "id": f"policy_exception-{now}",
        "schema": "policy_exception_log_v1",
        "created_at": now,
        "violated_rule": "역할 배분 초과",
        "role": role_row["role"],
        "label": role_row.get("label", role_row["role"]),
        "target_vs_actual": {
            "target_pct": role_row["target_pct"],
            "actual_pct": role_row["actual_pct"],
            "gap_pct": role_row["gap_pct"],
        },
        "reason": reason,
        "approved_at": now,
        "approved_by": approved_by,
    }


def append_and_save(record):
    """불변 저널 원칙 — 감사(audit) 위반이면 저장하지 않고 AuditViolation을
    던진다. 기존 레코드를 수정/삭제하는 함수는 이 파일에 없다."""
    violations = audit(record)
    if violations:
        raise AuditViolation(violations)
    log = load_json(LOG_FILE, {"schema": "policy_exception_log_v1", "records": []})
    log["records"].append(record)
    save_json(LOG_FILE, log)
    return record


def run_self_test():
    role_row = {"role": "스윙-전술", "label": "스윙-전술", "target_pct": 15, "actual_pct": 42.9, "gap_pct": -27.9}

    # 1) 정상 레코드 — 필드가 요청 스키마(event_id/violated_rule/target_vs_actual/
    #    reason/approved_at/approved_by)를 그대로 담고 있는지
    rec = build_record(role_row, "일시적 초과, 다음 리밸런싱까지 유지", "테스터 (id:12345)",
                       now="2026-08-30T00:00:00+00:00")
    print(f"[1] 레코드: {rec}")
    assert rec["role"] == "스윙-전술" and rec["target_vs_actual"]["gap_pct"] == -27.9
    assert rec["reason"] == "일시적 초과, 다음 리밸런싱까지 유지"
    assert rec["approved_by"] == "테스터 (id:12345)"
    assert audit(rec) == [], f"정상 레코드가 감사를 통과 못 함: {audit(rec)}"

    # 2) 금지 문구가 사유에 섞이면 AuditViolation을 던지고, 저장은 되지 않는지
    import os
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    bad_rec = build_record(role_row, "그래서 사도 될 것 같음", "테스터", now="2026-08-30T00:00:00+00:00")
    raised = False
    try:
        append_and_save(bad_rec)
    except AuditViolation as e:
        raised = True
        print(f"[2] 금지 문구 포함 레코드 -> AuditViolation: {e.violations}")
    assert raised, "금지 문구가 있는데 AuditViolation이 발생하지 않음"
    assert not os.path.exists(LOG_FILE), "감사 위반인데 파일이 저장됨(불변 저널 원칙 위반)"

    # 3) 정상 레코드는 append-only로 쌓이는지(기존 레코드를 건드리지 않는지)
    r1 = append_and_save(build_record(role_row, "사유1", "A", now="2026-08-30T00:00:00+00:00"))
    r2 = append_and_save(build_record(role_row, "사유2", "B", now="2026-08-30T01:00:00+00:00"))
    log = load_json(LOG_FILE, None)
    print(f"[3] 저장된 레코드 수: {len(log['records'])}")
    assert len(log["records"]) == 2
    assert log["records"][0]["id"] == r1["id"] and log["records"][1]["id"] == r2["id"]
    os.remove(LOG_FILE)

    print("\npolicy_exception.py 자체 검증 통과.")


if __name__ == "__main__":
    run_self_test()

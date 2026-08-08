"""킬스위치 긴급 반영 전용 초경량 스크립트 (2026-08-08).

poll.yml(전체 명령어 처리 — 오프셋을 실제로 전진시키는 "정식" 처리 경로)과 별개로,
GitHub Actions 스케줄 트리거의 실제 지연(관측치 40~90분, 플랫폼 자체의 부하 기반
지연이라 워크플로 설정만으로는 없앨 수 없음 — 인수인계 문서 참고)이 있는 동안
`/autoexec_stop`만이라도 최대한 빨리 반영하기 위한 별도 경로다.

**오프셋(telegram_offset.json)을 절대 전진시키지 않는다.** 이 파일은 poll.yml만
쓴다 — 이 스크립트는 poll.yml이 마지막으로 확정한 값을 읽기만 해서 그대로
`getUpdates`에 넘긴다. 그 값을 넘지 않는 한 텔레그램 서버 쪽 저수위표시가
전진하지 않으므로, 이 스크립트가 poll.yml이 아직 못 본 메시지를 "먼저 읽어서
없애버리는" 일이 생기지 않는다.

**발견해도 "정식 처리"는 하지 않는다.** 킬스위치만 즉시 켜고 짧은 확인 메시지만
보낸다. 중복 등록 방지, 정식 회신 문구, 오프셋 전진 등 나머지는 여전히 poll.yml의
다음 정규 주기가 담당한다 — 그래서 같은 `/autoexec_stop`에 대해 이 스크립트의
즉시 알림 하나, poll.yml의 정식 확인 하나, 총 두 번 알림이 갈 수 있다. 의도된
중복이다(`engage_kill_switch`는 멱등이라 두 번 걸어도 안전하다).

`/autoexec_start`(재개)는 이 빠른 경로에 포함하지 않는다 — 안전 기본값은
"멈춰 있는 쪽"이고, 재개가 몇 분 늦는 것과 정지가 몇 분 늦는 것은 리스크
크기가 다르다.
"""
import autoexec
from analyze_lib import TELEGRAM_TOKEN, load_json, requests, send_telegram

OFFSET_FILE = "telegram_offset.json"
STOP_COMMAND = "/autoexec_stop"


def peek_updates(offset):
    """poll.yml과 동일한 오프셋으로 조회만 한다 — 이 값보다 낮춰도, 저장해서도 안 됨."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 5}
    return requests.get(url, params=params, timeout=10).json()


def has_stop_command(updates_result):
    """순수 함수로 분리 — 네트워크 없이 self-test 가능하게."""
    for u in updates_result:
        text = (u.get("message", {}).get("text") or "").strip()
        if text.split()[:1] == [STOP_COMMAND]:
            return True
    return False


def run():
    offset_data = load_json(OFFSET_FILE, {"last_update_id": 0})
    offset = offset_data["last_update_id"] + 1

    updates = peek_updates(offset)
    if not updates.get("ok"):
        print("빠른경로: 피크 조회 실패", updates)
        return

    if not has_stop_command(updates.get("result", [])):
        print("빠른경로: /autoexec_stop 없음 (정식 처리는 poll.yml이 계속 담당)")
        return

    st = autoexec.load_state()
    already = autoexec.kill_switch_engaged(st)
    st = autoexec.engage_kill_switch(st)
    autoexec.save_json(autoexec.STATE_FILE, st)
    print(f"빠른경로: 킬스위치 {'이미 작동 중이었음' if already else '즉시 작동'}")

    send_telegram(
        "⚡ 킬스위치 긴급 반영(빠른경로)"
        + (" — 이미 작동 중이었음" if already else " — 즉시 작동")
        + "\n중복확인·오프셋 갱신 등 정식 처리는 다음 poll 주기에 이어집니다."
    )


def run_self_test():
    print("=== autoexec_stop_fast.py 자체 검증 (네트워크 미사용) ===\n")

    # 1) 정확히 일치하는 명령만 인식 (접미사 붙은 변형은 오탐 방지 위해 불인식으로 취급 —
    #    poll.yml이 어차피 정규 처리하므로 이 빠른 경로가 놓쳐도 안전 쪽으로 치우친 실패)
    assert has_stop_command([{"message": {"text": "/autoexec_stop"}}]) is True
    assert has_stop_command([{"message": {"text": " /autoexec_stop "}}]) is True
    print("[1] 정확히 일치하는 /autoexec_stop 인식")

    # 2) 관련 없는 명령/빈 업데이트는 무시
    assert has_stop_command([{"message": {"text": "/autoexec_status"}}]) is False
    assert has_stop_command([{"message": {"text": "/autoexec_start"}}]) is False
    assert has_stop_command([{}]) is False
    assert has_stop_command([]) is False
    print("[2] 무관한 명령/빈 업데이트 무시 확인")

    # 3) 여러 건 중 하나라도 있으면 인식
    assert has_stop_command([{"message": {"text": "/status"}},
                              {"message": {"text": "/autoexec_stop"}}]) is True
    print("[3] 배치 중 일부만 일치해도 인식")

    print("\n모든 자체 검증 통과.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="킬스위치 긴급 반영 전용 (offset 비전진)")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        run_self_test()
    else:
        run()

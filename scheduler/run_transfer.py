# 스케줄러 진입점: 미전송 세션을 압축 → VPN 연결 → SFTP 전송 → 검증 → VPN 해제.
#   - 이미 sent/ 에 있는 세션은 건너뜀(idempotent).
#   - Windows Task Scheduler 가 run_transfer.bat 을 통해 이 모듈을 호출한다.
#
# 실행: 프로젝트 루트에서  python -m scheduler.run_transfer
import os
import glob

from backend import transfer
from backend.vpn import vpn_session
from backend.config import RECORDINGS_DIR, SENT_DIR
from backend.logutil import log


def pending_sessions():
    """sent/ 밖에 있는, 아직 전송 안 된 세션 폴더(시작__종료)만 반환."""
    sent_abs = os.path.abspath(SENT_DIR)
    for d in glob.glob(os.path.join(RECORDINGS_DIR, "*__*")):
        if not os.path.isdir(d):
            continue
        if os.path.abspath(d).startswith(sent_abs):  # sent/ 하위 제외
            continue
        yield d


def main():
    sessions = list(pending_sessions())
    if not sessions:
        log("미전송 세션 없음 — 종료")
        return

    # VPN 연결 → (세션별) 압축·전송·검증·정리 → (with 종료 시) VPN 해제
    with vpn_session() as reachable:
        if not reachable:
            log("VPN 도달 실패 → 전송 생략, 다음 주기 재시도", "warning")
            return
        # 성공: zip 만 sent/ 보관 + 원본 폴더 삭제 / 실패: 폴더 잔류하여 재시도
        transfer.run(sessions)


if __name__ == "__main__":
    main()

# 역할: VPN 연결 확인 + (필요시) 자동 연결/해제. 스케줄러 무인 실행용.
#   동작 순서(연결-필요시-연결):
#     1) 이미 NAS 도달되면 → 그대로 사용 (사람이 켜뒀거나 상시연결 = A방식). 건드리지 않음.
#     2) 미연결 + VPN_AUTOMANAGE=1 → OpenVPN CLI 로 직접 연결하고, 작업 끝나면 해제 (B방식).
#     3) 미연결 + VPN_AUTOMANAGE=0 → 경고만 하고 이번 주기 전송 생략(다음 주기 재시도).
# ※ 자동 연결(2)을 쓰려면 OpenVPN "Community CLI"(openvpn.exe)와 .ovpn 파일이 필요하다.
#    지금처럼 OpenVPN Connect(GUI) 만 있으면 1번(상시연결) 방식으로 쓰는 게 안전하다.
import os
import socket
import subprocess
import time
import contextlib

from .config import (
    SFTP_HOST, SFTP_PORT, VPN_AUTOMANAGE,
    OPENVPN_EXE, OVPN_CONFIG, VPN_WAIT_SECONDS,
)
from .logutil import log


def host_reachable(timeout: int = 5) -> bool:
    """SFTP_HOST:SFTP_PORT(=VPN 터널 안의 NAS) TCP 도달 여부.
    VPN 미연결 시 10.8.0.1 은 어디에도 없으므로 여기서 걸러진다.
    """
    try:
        socket.create_connection((SFTP_HOST, SFTP_PORT), timeout=timeout).close()
        return True
    except OSError:
        return False


def _wait_reachable(deadline_s: int) -> bool:
    end = deadline_s
    while end > 0:
        if host_reachable():
            return True
        time.sleep(2)
        end -= 2
    return False


def connect() -> "subprocess.Popen | None":
    """연결-필요시-연결. 반환값이 not None 이면 '내가 띄운 것'이라 나중에 해제 대상."""
    # 1) 이미 연결돼 있으면(사람/상시연결) 그대로 사용 — 재연결 안 함
    if host_reachable():
        log("VPN 이미 연결됨 — 도달 확인")
        return None

    # 2) 미연결인데 자동관리도 꺼져 있으면 손 못 씀
    if not VPN_AUTOMANAGE:
        log("VPN 미연결(수동 모드) — 연결 후 재시도 필요", "warning")
        return None

    # 3) 미연결 + 자동관리 ON → OpenVPN CLI 로 직접 연결
    if not os.path.exists(OPENVPN_EXE):
        log(f"VPN 자동연결 불가 — OpenVPN 실행파일 없음: {OPENVPN_EXE}", "error")
        return None
    if not os.path.exists(OVPN_CONFIG):
        log(f"VPN 자동연결 불가 — .ovpn 설정 없음: {OVPN_CONFIG}", "error")
        return None

    log(f"VPN 미연결 → OpenVPN 자동 연결 시도: {OVPN_CONFIG}")
    proc = subprocess.Popen(
        [OPENVPN_EXE, "--config", OVPN_CONFIG],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if _wait_reachable(VPN_WAIT_SECONDS):
        log("VPN 연결 완료 — NAS 도달 확인")
        return proc
    # 연결 실패 → 띄운 프로세스 정리
    log("VPN 연결 실패(도달 불가) — 프로세스 종료", "error")
    _terminate(proc)
    return None


def disconnect(proc: "subprocess.Popen | None"):
    if proc is None:
        return
    log("OpenVPN 연결 해제")
    _terminate(proc)


def _terminate(proc: "subprocess.Popen"):
    with contextlib.suppress(Exception):
        proc.terminate()
        proc.wait(timeout=10)


@contextlib.contextmanager
def vpn_session():
    """with vpn_session() as ok: 형태로 연결→작업→해제 보장."""
    proc = connect()
    ok = host_reachable()
    try:
        yield ok
    finally:
        disconnect(proc)

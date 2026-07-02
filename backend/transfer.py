# 역할: 세션 압축 → SFTP 업로드(키 인증) → 무결성 검증 → 결과 정리 (idempotent).
#   보관 정책: 성공 시 zip 만 sent/ 로 남기고 원본 폴더는 삭제(무손실이라 복구 가능).
#             실패 시 zip 은 지우고 원본 폴더는 남겨 다음 주기에 재시도.
#   무결성: 원격에서 실제 sha256 을 계산해 로컬 해시와 비교(불가 시 크기 폴백).
import os
import shutil
import paramiko

from .config import (
    SFTP_HOST, SFTP_PORT, SFTP_USER, SFTP_KEY, SFTP_KEY_TYPE, SFTP_DEST, SENT_DIR,
)
from .session import sha256_file
from .archive import archive
from .vpn import host_reachable
from .logutil import log


def _load_key(path: str, key_type: str):
    """개인키 로드. key_type=auto 면 ed25519 → rsa 순으로 시도."""
    loaders = {
        "ed25519": paramiko.Ed25519Key,
        "rsa": paramiko.RSAKey,
    }
    if key_type in loaders:
        return loaders[key_type].from_private_key_file(path)
    last = None
    for loader in (paramiko.Ed25519Key, paramiko.RSAKey):
        try:
            return loader.from_private_key_file(path)
        except Exception as e:  # 형식 불일치는 다음 로더로
            last = e
    raise last


def _connect():
    """비밀번호 없이 개인키로 SFTP 연결. (SFTPClient, Transport) 반환."""
    key = _load_key(SFTP_KEY, SFTP_KEY_TYPE)
    t = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    t.connect(username=SFTP_USER, pkey=key)
    return paramiko.SFTPClient.from_transport(t), t


def _ensure_remote_dir(sftp, remote_dir: str):
    """대상 폴더가 없으면 상위부터 순차 생성(최소권한 폴더 내)."""
    parts, cur = remote_dir.strip("/").split("/"), ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)


def _remote_sha256(t: paramiko.Transport, remote_path: str) -> "str | None":
    """NAS 에서 sha256sum 을 실행해 원격 해시를 얻는다. 불가 시 None."""
    try:
        ch = t.open_session()
        ch.exec_command(f'sha256sum "{remote_path}"')
        out = ch.makefile("rb").read().decode(errors="ignore").strip()
        ch.recv_exit_status()
        if out:
            return out.split()[0]
    except Exception as e:
        log(f"원격 sha256 계산 불가(폴백 사용): {e}", "warning")
    return None


def _sha256_via_sftp(sftp: paramiko.SFTPClient, remote_path: str) -> str:
    """쉘 권한이 없는 SFTP 전용 계정용: 업로드된 원격 파일을 SFTP 로 다시 읽어
    SHA-256 을 계산한다(쉘 exec 없이도 진짜 무결성 검증 가능)."""
    import hashlib
    h = hashlib.sha256()
    with sftp.open(remote_path, "rb") as rf:
        rf.prefetch()  # 대용량 다운로드 속도 향상
        for b in iter(lambda: rf.read(1024 * 64), b""):
            h.update(b)
    return h.hexdigest()


def upload_one(zip_path: str) -> bool:
    """zip 하나 업로드 + 무결성 검증(SHA-256). 성공 True."""
    name = os.path.basename(zip_path)
    remote = f"{SFTP_DEST}/{name}"
    local_hash = sha256_file(zip_path)
    local_size = os.path.getsize(zip_path)

    sftp, t = _connect()
    try:
        _ensure_remote_dir(sftp, SFTP_DEST)
        sftp.put(zip_path, remote)

        # 1차: 크기 확인(빠른 실패)
        if sftp.stat(remote).st_size != local_size:
            raise IOError("size mismatch")

        # 2차: 원격 실제 SHA-256 대조.
        #   ① NAS 에서 sha256sum 실행(쉘 되는 계정) → ② 안 되면 SFTP 로 되읽어 해시.
        rhash = _remote_sha256(t, remote)
        method = "원격 sha256sum"
        if rhash is None:
            rhash = _sha256_via_sftp(sftp, remote)   # 쉘 없어도 되는 진짜 검증
            method = "SFTP 되읽기"

        if rhash.lower() != local_hash.lower():
            raise IOError(f"sha256 mismatch: local={local_hash} remote={rhash}")
        log(f"검증(SHA-256 일치, {method}): {name}")
        return True
    finally:
        sftp.close()
        t.close()


def _finalize_sent(zip_path: str, session_dir: str):
    """성공: zip 만 sent/ 로 남기고 원본 세션 폴더는 삭제(중복 방지·디스크 절약)."""
    os.makedirs(SENT_DIR, exist_ok=True)
    shutil.move(zip_path, os.path.join(SENT_DIR, os.path.basename(zip_path)))
    if os.path.isdir(session_dir):
        shutil.rmtree(session_dir)  # zip 으로 무손실 복구 가능하므로 원본 폴더 제거


def _cleanup_zip(zip_path: str):
    """실패: 최상단에 zip 이 남지 않도록 정리(폴더는 재시도 위해 유지)."""
    if os.path.exists(zip_path):
        os.remove(zip_path)


def _has_video(session_dir: str) -> bool:
    """세션에 실제 영상(cam_*.mp4, 0바이트 아님)이 하나라도 있는지."""
    for fn in os.listdir(session_dir):
        if fn.startswith("cam_") and fn.endswith(".mp4"):
            if os.path.getsize(os.path.join(session_dir, fn)) > 0:
                return True
    return False


def process_session(session_dir: str) -> bool:
    """세션 하나: 압축 → 업로드 → 검증 → 성공시 zip만 sent/·폴더삭제 / 실패시 zip정리."""
    name = os.path.basename(session_dir)

    # 가드: 영상 없는 빈 세션은 압축·전송하지 않는다(빈 zip 이 NAS 로 가는 것 방지).
    if not _has_video(session_dir):
        log(f"빈 세션(영상 없음) 전송 생략: {name}", "warning")
        return False

    try:
        zip_path, _ = archive(session_dir)  # 폴더 옆에 잠깐 생김(성공/실패 시 정리됨)
    except Exception as e:
        log(f"압축 실패, 다음 주기 재시도: {name} - {e}", "error")
        return False

    try:
        if upload_one(zip_path):
            _finalize_sent(zip_path, session_dir)
            log(f"전송 성공(zip 보관): {os.path.basename(zip_path)}")
            return True
    except Exception as e:
        log(f"전송 실패, 다음 주기 재시도: {name} - {e}", "error")

    _cleanup_zip(zip_path)  # 실패분 zip 은 지워 최상단을 깔끔히 유지
    return False


def run(session_dirs: list[str]):
    """미전송 세션 폴더 목록을 순회 처리. 실패분은 폴더로 남겨 다음 주기 재시도."""
    if not session_dirs:
        log("전송 대상 없음")
        return
    if not host_reachable():
        log("VPN 미연결(NAS 도달 불가) → 전송 중단, 다음 주기 재시도", "warning")
        return

    for session_dir in session_dirs:
        process_session(session_dir)

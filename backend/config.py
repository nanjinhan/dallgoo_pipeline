# 역할: .env 를 로드해 설정값을 상수로 노출한다.
#       비밀값·경로는 여기(=환경변수)에서만 읽고, 코드에 하드코딩하지 않는다.
import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트(.env 위치) 기준으로 로드
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_bool(name: str, default: bool = False) -> bool:
    v = _get(name, "1" if default else "0").lower()
    return v in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    try:
        return int(_get(name) or default)
    except ValueError:
        return default


# --- go2rtc / 백엔드 ---
GO2RTC_URL = _get("GO2RTC_URL", "http://localhost:1984")
BACKEND_HOST = _get("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = _get_int("BACKEND_PORT", 8000)

# RECORDINGS_DIR 은 상대경로면 프로젝트 루트 기준 절대경로로 정규화
_rec = _get("RECORDINGS_DIR", "./recordings")
RECORDINGS_DIR = str((ROOT / _rec).resolve()) if not os.path.isabs(_rec) else _rec

# CAMERAS: "cam_1,cam_2" -> {cam_id: stream_name}. stream_name = cam_id (go2rtc 키와 일치)
_cams = [c.strip() for c in _get("CAMERAS", "cam_1").split(",") if c.strip()]
CAMERAS = {c: c for c in _cams}

# --- SFTP / NAS ---
SFTP_HOST = _get("SFTP_HOST")
SFTP_PORT = _get_int("SFTP_PORT", 2222)
SFTP_USER = _get("SFTP_USER")
SFTP_KEY = _get("SFTP_KEY")
SFTP_DEST = _get("SFTP_DEST")
SFTP_KEY_TYPE = _get("SFTP_KEY_TYPE", "auto").lower()  # ed25519 | rsa | auto

# --- VPN 자동 연결/해제 ---
VPN_AUTOMANAGE = _get_bool("VPN_AUTOMANAGE", False)
OPENVPN_EXE = _get("OPENVPN_EXE")
OVPN_CONFIG = _get("OVPN_CONFIG")
VPN_WAIT_SECONDS = _get_int("VPN_WAIT_SECONDS", 30)

# 파생 경로
SENT_DIR = os.path.join(RECORDINGS_DIR, "sent")
LOGS_DIR = str(ROOT / "logs")

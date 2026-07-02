# 역할: 웹에서 녹화 제어. 세션 = start~stop 한 묶음. 카메라별 스레드 관리.
import os
import threading
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import GO2RTC_URL, RECORDINGS_DIR, CAMERAS
from .recorder import CameraRecorder
from . import session as sess
from .archive import archive
from .logutil import log

app = FastAPI(title="recording-pipeline")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

# 동시 start/stop 경합 방지
_LOCK = threading.Lock()
STATE: dict = {}
# 마지막 세션의 압축 진행 상태: {"folder","state","zip","sha256"}
#   state: "archiving" | "done" | "error"
ARCHIVE: dict = {}


def _archive_bg(folder_path: str):
    """녹화 중지 후 백그라운드로 세션 폴더를 압축한다(파일 준비 완료 → 바로 압축)."""
    name = os.path.basename(folder_path)
    try:
        zip_path, zhash = archive(folder_path)
        ARCHIVE.clear()
        ARCHIVE.update(folder=name, state="done",
                       zip=os.path.basename(zip_path), sha256=zhash)
        log(f"압축 완료: {os.path.basename(zip_path)}")
    except Exception as e:
        ARCHIVE.clear()
        ARCHIVE.update(folder=name, state="error", zip=None, error=str(e))
        log(f"압축 실패: {name} - {e}", "error")


def stream_mp4(stream_name: str) -> str:
    # go2rtc 무손실 remux MP4 엔드포인트 (정확한 경로는 go2rtc 대시보드에서 확인)
    return f"{GO2RTC_URL}/api/stream.mp4?src={stream_name}"


@app.get("/")
def index():
    web = os.path.join(os.path.dirname(__file__), "..", "web", "index.html")
    # 페이지 수정 후 새로고침하면 항상 최신 HTML 이 뜨도록 캐시 금지
    return FileResponse(os.path.abspath(web), headers={"Cache-Control": "no-store"})


@app.get("/cameras")
def cameras():
    return {"cameras": list(CAMERAS.keys())}


@app.get("/status")
def status():
    return {
        "recording": bool(STATE.get("recording")),
        "start": STATE["start"].isoformat() if STATE.get("start") else None,
        "cameras": list(CAMERAS.keys()),
        "archive": dict(ARCHIVE) if ARCHIVE else None,  # 최근 세션 압축 진행/결과
    }


@app.post("/start")
def start():
    with _LOCK:
        if STATE.get("recording"):
            return {"status": "already_recording"}

        start_at = datetime.now()
        tmp = os.path.join(RECORDINGS_DIR, f"_tmp_{start_at:%Y%m%d_%H%M%S}")
        os.makedirs(tmp, exist_ok=True)

        recorders = {}
        for cam_id, stream_name in CAMERAS.items():
            rec = CameraRecorder(
                cam_id, stream_mp4(stream_name),
                os.path.join(tmp, f"{cam_id}.mp4"),
            )
            rec.start()
            recorders[cam_id] = rec

        STATE.update(recording=True, start=start_at, tmp=tmp, recorders=recorders)
        log(f"세션 시작: {start_at:%Y%m%d_%H%M%S} cams={list(CAMERAS.keys())}")
        return {"status": "recording", "cameras": list(CAMERAS.keys())}


@app.post("/stop")
def stop():
    with _LOCK:
        if not STATE.get("recording"):
            return {"status": "not_recording"}

        for rec in STATE["recorders"].values():
            rec.stop()
        end_at = datetime.now()
        folder = sess.finalize(
            RECORDINGS_DIR, STATE["tmp"], STATE["start"], end_at,
            list(CAMERAS.keys()),
        )
        STATE.clear()
        name = os.path.basename(folder)

        # 파일 준비 완료(finalize) → 바로 압축 시작(백그라운드, 큰 파일도 응답 안 막힘)
        ARCHIVE.clear()
        ARCHIVE.update(folder=name, state="archiving", zip=None)
        threading.Thread(target=_archive_bg, args=(folder,), daemon=True).start()

        log(f"세션 확정: {folder} → 압축 시작")
        return {"status": "stopped", "folder": name, "archive": "archiving"}

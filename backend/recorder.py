# 역할: go2rtc 의 무손실 remux MP4 스트림을 파일로 그대로 받아 적는다 (재인코딩 X).
#       카메라당 1스레드. 중지 신호(threading.Event)로 정지한다.
import threading
import requests
from .logutil import log


def record(stream_url: str, filepath: str, stop_event: threading.Event):
    """stream_url(go2rtc stream.mp4)을 filepath 로 스트리밍 저장.

    네트워크·파일 IO 는 실패 가능 지점 → 예외를 잡아 로깅한다(스펙 §0).
    stop_event 가 set 되면 다음 청크 경계에서 멈춘다.
    """
    try:
        with requests.get(stream_url, stream=True, timeout=(10, None)) as r:
            r.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if stop_event.is_set():
                        break
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        log(f"녹화 오류 [{filepath}]: {e}", "error")


class CameraRecorder:
    def __init__(self, cam_id: str, stream_url: str, out_path: str):
        self.cam_id = cam_id
        self.out_path = out_path
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=record, args=(stream_url, out_path, self._stop), daemon=True
        )

    def start(self):
        log(f"녹화 시작: {self.cam_id} -> {self.out_path}")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=10)
        log(f"녹화 중지: {self.cam_id}")

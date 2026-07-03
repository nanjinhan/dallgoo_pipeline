# 역할: go2rtc 의 무손실 remux MP4 스트림을 파일로 그대로 받아 적는다 (재인코딩 X).
#       카메라당 1스레드. 중지 신호(threading.Event)로 정지한다.
#       ★ 마네킹 센서 동기화용: 실제 첫 영상 데이터가 도착한 벽시계 시각을 기록한다.
#         (버튼 누른 시각과 실제 영상 시작 시각은 스트림 시작 지연만큼 차이가 난다.)
import threading
from datetime import datetime
import requests
from .logutil import log


class CameraRecorder:
    def __init__(self, cam_id: str, stream_url: str, out_path: str):
        self.cam_id = cam_id
        self.stream_url = stream_url
        self.out_path = out_path
        # 실제 첫 영상 데이터가 들어온 시각(=영상 0초의 벽시계 시각). 동기화 기준점.
        self.first_frame_at: "datetime | None" = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        """스트림을 파일로 저장. 네트워크·파일 IO 실패는 잡아 로깅(스펙 §0)."""
        try:
            with requests.get(self.stream_url, stream=True, timeout=(10, None)) as r:
                r.raise_for_status()
                with open(self.out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 64):
                        if self._stop.is_set():
                            break
                        if chunk:
                            if self.first_frame_at is None:
                                # 첫 실데이터 도착 시각 = 이 영상의 시간 0점
                                self.first_frame_at = datetime.now()
                            f.write(chunk)
        except Exception as e:
            log(f"녹화 오류 [{self.out_path}]: {e}", "error")

    def start(self):
        log(f"녹화 시작: {self.cam_id} -> {self.out_path}")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=10)
        log(f"녹화 중지: {self.cam_id}")

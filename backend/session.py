# 역할: 세션 폴더 확정 + packet.json + checksums.sha256 생성.
#       폴더명 규칙: 시작시각__종료시각 (콜론 금지, 파일시스템 안전 포맷).
import os
import json
import hashlib


def sha256_file(path: str) -> str:
    """파일의 SHA-256 16진 해시. 대용량 대비 64KB 스트리밍."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 64), b""):
            h.update(b)
    return h.hexdigest()


def finalize(root, tmp_dir, start_at, end_at, cameras, video_starts=None) -> str:
    """임시 녹화 폴더(tmp_dir)를 '시작__종료' 세션 폴더로 확정하고
    packet.json, checksums.sha256 을 기록한 뒤 최종 경로를 돌려준다.

    video_starts: {cam_id: datetime|None} — 각 카메라의 실제 첫 프레임 시각.
      마네킹 센서 데이터를 영상에 맞출 때 이 값을 시간 0점으로 쓴다.
    """
    name = f"{start_at:%Y%m%d_%H%M%S}__{end_at:%Y%m%d_%H%M%S}"  # 콜론 금지
    final = os.path.join(root, name)
    os.rename(tmp_dir, final)

    # --- 카메라별 영상 타이밍(동기화 기준) 계산 ---
    #   start   : 실제 첫 프레임 벽시계 시각 (영상 0초). 센서 데이터 정렬 기준.
    #   duration_sec : 실제 녹화된 영상 길이(첫 프레임~중지). 버튼시간이 아님.
    video_starts = video_starts or {}
    video = {}
    for cam in cameras:
        fa = video_starts.get(cam)
        if fa:
            video[cam] = {
                "start": fa.isoformat(),
                "duration_sec": round((end_at - fa).total_seconds(), 3),
            }
        else:
            video[cam] = {"start": None, "duration_sec": 0}  # 영상 못 받음

    # --- packet.json: 세션 메타 + 영상 타이밍 + 마네킹 패킷 자리(빈 배열) ---
    meta = {
        "session_start": start_at.isoformat(),   # 버튼 누른 시각(참고용)
        "session_end": end_at.isoformat(),       # 중지 누른 시각
        "cameras": cameras,
        "video": video,                          # ★ 카메라별 실제 영상 시작·길이(동기화 기준)
        "manikin_packets": [],                   # 추후 마네킹 패킷을 이 배열에 병합
    }
    with open(os.path.join(final, "packet.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # --- checksums.sha256: 폴더 내 각 파일 무결성 (표준 sha256sum 포맷) ---
    lines = []
    for fn in sorted(os.listdir(final)):
        if fn == "checksums.sha256":
            continue
        lines.append(f"{sha256_file(os.path.join(final, fn))}  {fn}")
    with open(os.path.join(final, "checksums.sha256"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return final

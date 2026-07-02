# 역할: 세션 폴더를 무손실 ZIP(Deflate)으로 압축 + 압축본 SHA-256 생성.
#       영상은 이미 압축 코덱이므로 컨테이너만 묶는다(재인코딩 X).
import os
import zipfile
from .session import sha256_file


def _zip_is_fresh(session_dir: str, zip_path: str) -> bool:
    """zip 이 이미 있고, 폴더의 어떤 파일보다 최신이면 재압축 불필요."""
    if not os.path.exists(zip_path):
        return False
    zip_mtime = os.path.getmtime(zip_path)
    for r, _, files in os.walk(session_dir):
        for fn in files:
            if os.path.getmtime(os.path.join(r, fn)) > zip_mtime:
                return False
    return True


def archive(session_dir: str, force: bool = False) -> tuple[str, str]:
    """session_dir 을 session_dir.zip 으로 압축하고 (zip경로, sha256) 반환.

    이미 최신 zip 이 있으면 재사용한다(녹화 중지 때 만든 zip 을 전송 단계에서 재압축하지 않음).
    force=True 면 무조건 다시 압축한다.
    """
    zip_path = session_dir.rstrip("/\\") + ".zip"

    if not force and _zip_is_fresh(session_dir, zip_path):
        return zip_path, sha256_file(zip_path)  # 이미 준비된 zip 재사용

    tmp_path = zip_path + ".part"
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z:  # 무손실
        for r, _, files in os.walk(session_dir):
            for fn in files:
                full = os.path.join(r, fn)
                z.write(full, os.path.relpath(full, session_dir))

    # 완성본만 최종 이름으로 (쓰다 만 zip 이 전송되는 것 방지)
    os.replace(tmp_path, zip_path)
    return zip_path, sha256_file(zip_path)

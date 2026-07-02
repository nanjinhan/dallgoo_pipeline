# 역할: 파일 + 콘솔 공용 로거. 전송/오류 이력을 logs/ 에 남긴다(스펙 §0).
import logging
import os
from logging.handlers import RotatingFileHandler
from .config import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

_logger = logging.getLogger("pipeline")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = RotatingFileHandler(
        os.path.join(LOGS_DIR, "pipeline.log"),
        maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    fh.setFormatter(fmt)
    _logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    _logger.addHandler(ch)


def log(msg: str, level: str = "info"):
    getattr(_logger, level, _logger.info)(msg)

import logging
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "log")
LOG_DIR = os.path.normpath(LOG_DIR)

def _log_file(name: str) -> str:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d")
    return os.path.join(LOG_DIR, f"{name}_{ts}.log")

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fh = logging.FileHandler(_log_file(name), encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)
    logger.propagate = False
    return logger

def get_pipeline_logger() -> logging.Logger:
    return setup_logger("pipeline")

def get_task_logger() -> logging.Logger:
    return setup_logger("task")
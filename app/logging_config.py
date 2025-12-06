
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging():
    """
    - Console + file (logs/app.log)
    - Rotate to avoid infinite growth
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    level = os.getenv("LOG_LEVEL", "INFO").upper()

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(level)

    # Prevent duplicate handlers
    if root.handlers:
        return

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,  
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root.addHandler(console)
    root.addHandler(file_handler)

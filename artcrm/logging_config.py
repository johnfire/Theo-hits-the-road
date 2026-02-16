"""
Logging configuration for Art CRM.

Single 'artcrm' logger used across all modules.

  Log file : logs/artcrm.log
  Rotation : 5 MB × 3 backups
  Level    : LOG_LEVEL env var (DEBUG / INFO / WARNING / ERROR / CRITICAL)
             defaults to INFO when unset

Usage
-----
    from artcrm.logging_config import configure_logging, log_call

    # Once at startup (idempotent — safe to call multiple times):
    configure_logging()

    # On any function you want traced:
    @log_call
    def my_function(arg1, arg2):
        ...

Log format per line
-------------------
    2026-02-16 14:32:01 | INFO     | CALL contacts_list | args=(type=None, status=None)
    2026-02-16 14:32:01 | INFO     | OK   contacts_list | 42ms
    2026-02-16 14:32:01 | ERROR    | FAIL contacts_list | ValueError: bad input | 3ms
"""

import functools
import logging
import logging.handlers
import os
import time
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "artcrm.log"
_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3


def configure_logging() -> logging.Logger:
    """
    Set up the artcrm logger. Idempotent — safe to call on every CLI entry.
    Returns the configured logger.
    """
    _LOG_DIR.mkdir(exist_ok=True)

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger("artcrm")

    # Guard: don't add duplicate handlers if already configured
    if logger.handlers:
        return logger

    logger.setLevel(level)

    handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
    logger.addHandler(handler)

    return logger


def log_call(func):
    """
    Decorator: logs entry, clean exit, and exceptions for any function.

    - DEBUG on entry   : CALL <name> | args=(...)
    - INFO  on success : OK   <name> | <N>ms
    - ERROR on failure : FAIL <name> | ExcType: message | <N>ms   (then re-raises)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger("artcrm")
        name = func.__name__
        start = time.perf_counter()

        # Build a readable argument string
        parts = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
        arg_str = ", ".join(parts) if parts else "—"
        logger.debug(f"CALL {name} | args=({arg_str})")

        try:
            result = func(*args, **kwargs)
            ms = int((time.perf_counter() - start) * 1000)
            logger.info(f"OK   {name} | {ms}ms")
            return result
        except Exception as exc:
            ms = int((time.perf_counter() - start) * 1000)
            logger.error(f"FAIL {name} | {type(exc).__name__}: {exc} | {ms}ms")
            raise

    return wrapper

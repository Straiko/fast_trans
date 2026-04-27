"""
Centralized logging for Olympus.

Uses Python's stdlib logging with a console handler by default, and an
optional rotating file handler in the XDG state directory. Replaces
scattered ``print()`` calls with structured, levelled logs.

Environment variables:
    OLYMPUS_LOG_LEVEL  — DEBUG / INFO / WARNING / ERROR (default INFO)
    OLYMPUS_LOG_FILE   — path to log file (default: ~/.local/state/olympus/olympus.log)
                          set to empty string to disable file logging
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False
_DEFAULT_LOG_DIR = Path.home() / ".local" / "state" / "olympus"
_DEFAULT_LOG_FILE = _DEFAULT_LOG_DIR / "olympus.log"


def _resolve_level() -> int:
    raw = (os.environ.get("OLYMPUS_LOG_LEVEL") or "INFO").strip().upper()
    return getattr(logging, raw, logging.INFO)


def _resolve_log_file() -> Path | None:
    raw = os.environ.get("OLYMPUS_LOG_FILE")
    if raw is None:
        return _DEFAULT_LOG_FILE
    raw = raw.strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def configure(force: bool = False) -> None:
    """Idempotently configure the root logger. Safe to call many times."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    root = logging.getLogger()
    root.setLevel(_resolve_level())

    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    log_file = _resolve_log_file()
    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:
            root.warning("Could not open log file %s: %s", log_file, exc)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, configuring root handlers lazily."""
    if not _CONFIGURED:
        configure()
    return logging.getLogger(name)

# ============================================================
# utils/logger.py — Structured JSON Logging
# ============================================================
# Provides a singleton logger that emits structured log
# records (JSON in production, pretty text in development).
# Logs: Resume Upload, AI Request, Cache Hit/Miss, DB Write,
#        Interview Scheduled, Errors.
# ============================================================

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from backend.config import settings


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # Merge structured extra fields
        for key, value in getattr(record, "_structured_extra", {}).items():
            log_entry[key] = value
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        base = f"{ts} [{record.levelname}] {record.name}:{record.lineno} — {record.getMessage()}"
        extra = getattr(record, "_structured_extra", {})
        if extra:
            base += f"  {json.dumps(extra, default=str)}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


class StructuredLogger(logging.Logger):
    """Logger subclass with a `.struct()` helper for extra fields."""

    def _log_structured(self, level, msg, extra: dict | None = None, **kwargs):
        super()._log(
            level,
            msg,
            args=(),
            extra={"_structured_extra": extra or {}},
            **kwargs,
        )

    def struct(self, level: int, msg: str, **fields):
        self._log_structured(level, msg, extra=fields)

    def event(self, event: str, level: int = logging.INFO, **fields):
        """Log a named business event with structured fields."""
        self._log_structured(level, f"EVENT:{event}", extra={"event": event, **fields})


def setup_logging() -> StructuredLogger:
    """Configure and return the root application logger."""
    logging.setLoggerClass(StructuredLogger)

    logger = logging.getLogger("resume_screening")
    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    if settings.app_env == "production":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter())
    logger.addHandler(handler)

    return logger  # type: ignore[return-value]


# Module-level singleton
logger = setup_logging()

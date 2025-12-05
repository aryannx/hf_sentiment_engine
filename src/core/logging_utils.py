from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional


def _json_formatter(record: logging.LogRecord) -> str:
    payload = {
        "ts": datetime.utcnow().isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "msg": record.getMessage(),
    }
    if hasattr(record, "extra_fields"):
        payload.update(record.extra_fields)
    return json.dumps(payload)


def get_json_logger(name: str, level: str = "INFO", extra: Optional[Dict[str, Any]] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
            record.extra_fields = extra or {}
            return _json_formatter(record)

    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_json(name: str, msg: str, level: str = "info", **fields: Any) -> None:
    logger = get_json_logger(name)
    getattr(logger, level.lower(), logger.info)(msg, extra={"extra_fields": fields})


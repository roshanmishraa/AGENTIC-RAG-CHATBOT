from __future__ import annotations
import logging
import sys
import json
from datetime import datetime

from app.settings import settings


class JSONFormatter(logging.Formatter):
    """Structured JSON logs — production systems need machine-parseable logs
    (for log aggregators like CloudWatch, Datadog, etc.), not plain text."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach any extra context passed via logger.info(msg, extra={...})
        for key in ("user_id", "chat_id", "request_id", "model_used", "duration_ms"):
            if hasattr(record, key):
                log_obj[key] = getattr(record, key)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    if settings.APP_ENV == "production":
        handler.setFormatter(JSONFormatter())
    else:
        # Human-readable in dev — easier to eyeball while testing locally
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))

    root_logger.handlers = [handler]

    # Quiet down noisy third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
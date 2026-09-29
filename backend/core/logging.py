import logging
import sys
import json
from backend.core.config import settings


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def setup_logging() -> logging.Logger:
    log_level_str = getattr(settings, "LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    env = getattr(settings, "ENVIRONMENT", "development").lower()

    if env == "production":
        formatter: logging.Formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if not root_logger.handlers:
        root_logger.addHandler(console_handler)

    return logging.getLogger("backend")


logger = setup_logging()

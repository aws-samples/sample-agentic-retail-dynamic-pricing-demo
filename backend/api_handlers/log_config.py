"""Structured JSON logging configuration for Lambda handlers.

Configures the root logger to output JSON-formatted log lines compatible
with CloudWatch Logs Insights queries. Each log entry includes:
- timestamp (ISO 8601)
- level (INFO, WARNING, ERROR, etc.)
- message
- logger name
- AWS request ID (when available from Lambda context)

Usage in handlers:
    from log_config import configure_logging
    logger = configure_logging(__name__)
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON for CloudWatch Logs Insights."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            Single-line JSON string with structured log data.
        """
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include function name from Lambda context if available
        function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        if function_name:
            log_entry["function_name"] = function_name

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def configure_logging(name: str = __name__) -> logging.Logger:
    """Configure structured JSON logging for a Lambda handler.

    Replaces the default Lambda log formatter with a JSON formatter.
    Safe to call multiple times — skips reconfiguration if already set up.

    Args:
        name: Logger name (typically __name__ from the calling module).

    Returns:
        Configured logger instance.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Only reconfigure if we haven't already added our JSON handler
    if not any(
        isinstance(h.formatter, JsonFormatter) for h in root_logger.handlers
    ):
        # Remove existing handlers (Lambda adds a default one)
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Add JSON handler writing to stdout
        json_handler = logging.StreamHandler(sys.stdout)
        json_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(json_handler)

    return logging.getLogger(name)

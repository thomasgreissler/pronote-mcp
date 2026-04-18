from __future__ import annotations

import logging
import re
import sys


class SensitiveFilter(logging.Filter):
    PATTERNS = [
        (re.compile(r"(password=)[^&\s'\"]+", re.IGNORECASE), r"\1[REDACTED]"),
        (re.compile(r"(Bearer\s+)[\w\-.]+"), r"\1[REDACTED]"),
        (re.compile(r"(Cookie:\s*)[^\r\n]+", re.IGNORECASE), r"\1[REDACTED]"),
        (re.compile(r"(Set-Cookie:\s*)[^\r\n]+", re.IGNORECASE), r"\1[REDACTED]"),
        (re.compile(r"(token['\"]?\s*[:=]\s*['\"]?)[\w\-.]+", re.IGNORECASE), r"\1[REDACTED]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern, repl in self.PATTERNS:
            msg = pattern.sub(repl, msg)
        record.msg = msg
        record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    handler.addFilter(SensitiveFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

"""Application-wide logging configuration, applied at process startup."""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # already configured (e.g. re-import under uvicorn --reload)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", "%H:%M:%S"))
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy third-party loggers down to WARNING.
    for noisy in ("httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

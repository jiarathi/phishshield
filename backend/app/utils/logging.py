import logging
import sys

def configure_logging() -> None:
    # Minimal logs; avoid logging user message content by default.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

"""Standalone durable campaign worker: ``python -m app.modules.campaigns.worker``."""

import asyncio
import logging
import os
import socket
import time

from app.db.session import SessionLocal
from app.modules.campaigns.service import process_campaign

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("intelapi.campaign-worker")
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def main() -> None:
    while True:
        try:
            with SessionLocal() as db:
                worked = asyncio.run(process_campaign(db, WORKER_ID))
            if not worked:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Campaign worker stopped")
            return
        except Exception:
            logger.exception("Campaign worker iteration failed")
            time.sleep(2)


if __name__ == "__main__":
    main()

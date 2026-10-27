from __future__ import annotations

import logging

from redis import Redis
from rq import Queue

from app.config import settings

logger = logging.getLogger(__name__)


def enqueue(func_path: str, *args) -> None:
    connection = Redis.from_url(settings.redis_url)
    queue = Queue(settings.queue_name, connection=connection)
    queue.enqueue(func_path, *args, job_timeout=settings.pdf_job_timeout_seconds)


def try_enqueue(func_path: str, *args) -> None:
    try:
        enqueue(func_path, *args)
    except Exception:
        logger.exception("could not enqueue %s", func_path)

import sys

from redis import Redis
from rq import Queue, SimpleWorker, Worker

from app.config import settings


def main() -> None:
    connection = Redis.from_url(settings.redis_url)
    queue = Queue(settings.queue_name, connection=connection)
    worker_cls = SimpleWorker if sys.platform == "darwin" else Worker
    worker_cls([queue], connection=connection).work()


if __name__ == "__main__":
    main()

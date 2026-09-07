from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "fraudmap",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    # A trace that has run for 20 minutes is not going to finish. The
    # soft limit lets the task raise and record an honest failure; the
    # hard limit kills a worker wedged in a call that ignores the soft
    # one, so a stuck fetch cannot occupy a slot indefinitely.
    task_soft_time_limit=1200,
    task_time_limit=1320,

    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)

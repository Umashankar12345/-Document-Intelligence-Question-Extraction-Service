from celery import Celery
from app.config import settings

celery_app = Celery(
    "pragati_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

is_eager = bool(int(getattr(settings, "celery_task_always_eager", 0)))

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=is_eager,
    broker_connection_timeout=1.0,
    broker_connection_max_retries=1,
    broker_connection_retry_on_startup=False,
    broker_transport_options={
        "socket_timeout": 1.0,
        "socket_connect_timeout": 1.0,
    },
)

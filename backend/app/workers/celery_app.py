from celery import Celery

from app.config import get_settings

settings = get_settings()
celery = Celery(
    "piae",
    broker=settings.redis_url or "redis://localhost:6379/0",
    backend=settings.redis_url or "redis://localhost:6379/0",
)


@celery.task(name="piae.investigate")
def investigate_task(investigation_id: str, job_id: str) -> None:
    from app.config import get_settings
    from app.db import init_db

    init_db(get_settings())
    from app.services.pipeline import run_pipeline

    run_pipeline(investigation_id, job_id)

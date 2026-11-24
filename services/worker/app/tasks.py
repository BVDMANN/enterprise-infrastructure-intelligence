"""Example tasks (PHASE 0).

Only real, side-effect-free tasks exist so far. Inventory sync, metric
ingestion and notification tasks arrive in PHASE 1.
"""

from app.celery_app import celery_app


@celery_app.task(name="eii.healthcheck")
def healthcheck() -> dict[str, str]:
    """Return worker liveness. No fake data: this reports the worker itself."""
    return {"status": "ok", "worker": "eii_worker"}

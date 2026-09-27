try:
    from .celery import app as celery_app
except ModuleNotFoundError as exc:
    # Keep Django management commands usable in minimal environments; the
    # worker image installs Celery from requirements.txt.
    if exc.name != "celery":
        raise
    celery_app = None

__all__ = ("celery_app",)

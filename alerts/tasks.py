"""Scheduled Celery tasks for evaluating active user alerts."""
import logging

from celery import shared_task

from alerts.models import Alert
from alerts.services import trigger_alert

logger = logging.getLogger(__name__)


@shared_task(name="alerts.evaluate_active_alerts")
def evaluate_active_alerts():
    """Evaluate each active alert and deliver notifications when conditions match."""
    alert_ids = Alert.objects.filter(is_active=True).values_list("id", flat=True)
    evaluated = 0
    triggered = 0
    failed = 0
    for alert_id in alert_ids.iterator(chunk_size=500):
        try:
            triggered += int(trigger_alert(alert_id))
            evaluated += 1
        except Alert.DoesNotExist:
            continue
        except Exception:
            failed += 1
            logger.exception("Alert evaluation failed for alert %s", alert_id)
    return {"evaluated": evaluated, "triggered": triggered, "failed": failed}

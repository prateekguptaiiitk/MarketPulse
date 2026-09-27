"""Notification delivery adapters for email and HTTPS webhooks."""
import ipaddress
import logging
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def deliver_alert(alert, payload):
    """Send an alert to its configured channel, raising delivery failures."""
    subject = f"MarketPulse alert: {alert.name} ({alert.instrument.symbol})"
    if alert.notification_channel == alert.NotificationChannel.EMAIL:
        sent = send_mail(subject, str(payload), settings.DEFAULT_FROM_EMAIL, [alert.user.email], fail_silently=False)
        if sent != 1:
            raise RuntimeError("Email backend did not accept the alert message.")
        return
    if alert.notification_channel == alert.NotificationChannel.WEBHOOK:
        _validate_webhook_url(alert.webhook_url)
        response = requests.post(
            alert.webhook_url,
            json=payload,
            timeout=getattr(settings, "WEBHOOK_TIMEOUT", 10),
            headers={"User-Agent": "MarketPulse-Alerts/1.0"},
        )
        response.raise_for_status()
        return
    raise ValueError(f"Unsupported notification channel: {alert.notification_channel}")


def _validate_webhook_url(url: str) -> None:
    """Restrict webhooks to HTTPS public hosts to avoid obvious SSRF targets."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Webhook URLs must use HTTPS and cannot contain embedded credentials.")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Webhook URLs cannot target local hostnames.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("Webhook URLs cannot target private, reserved, or loopback IP addresses.")

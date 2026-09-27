"""Production settings with secure defaults."""
from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, SECRET_KEY
from django.core.exceptions import ImproperlyConfigured

DEBUG = False
if SECRET_KEY == "unsafe-development-key-change-me" or len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("Production requires a strong SECRET_KEY of at least 50 characters.")
if not ALLOWED_HOSTS or ALLOWED_HOSTS == ["localhost", "127.0.0.1"]:
    raise ImproperlyConfigured("Production requires explicit ALLOWED_HOSTS.")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"

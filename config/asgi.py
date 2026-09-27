"""ASGI config for HTTP and Channels traffic."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django_asgi_app = get_asgi_application()


def create_application():
    """Build the HTTP and WebSocket protocol router after Django app setup."""
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import OriginValidator
    from django.conf import settings

    from realtime.middleware import JWTAuthMiddleware
    from realtime.routing import websocket_urlpatterns

    return ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": OriginValidator(JWTAuthMiddleware(URLRouter(websocket_urlpatterns)), settings.ALLOWED_HOSTS),
    })


application = create_application()

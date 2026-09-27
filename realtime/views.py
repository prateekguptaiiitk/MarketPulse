"""Manual WebSocket testing page."""
from django.shortcuts import render


def websocket_test_page(request):
    """Render a minimal browser page for manually inspecting price updates."""
    return render(request, "realtime/websocket_test.html")

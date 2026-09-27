"""Consistent error response envelopes for all DRF API exceptions."""
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Wrap DRF errors in a stable ``error`` object for API clients."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    original = response.data
    if isinstance(original, dict) and "detail" in original:
        message = str(original["detail"])
        details = None
    else:
        message = "Request validation failed."
        details = original
    response.data = {
        "error": {
            "status": response.status_code,
            "message": message,
            "details": details,
        }
    }
    return response

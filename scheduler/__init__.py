# scheduler package — lazy imports to avoid Google API import errors at startup
__all__ = ["get_email_service", "get_calendar_service"]


def __getattr__(name):
    if name == "get_email_service":
        from .gmail import get_email_service
        return get_email_service
    if name == "get_calendar_service":
        from .google_calendar import get_calendar_service
        return get_calendar_service
    raise AttributeError(f"module 'scheduler' has no attribute '{name}'")

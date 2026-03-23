from dashboard.api.printers import router as printers_router
from dashboard.api.jobs import router as jobs_router
from dashboard.api.analytics import router as analytics_router

__all__ = ["printers_router", "jobs_router", "analytics_router"]

"""Flask route package for the application UI and HTTP API."""

from .profiles import profiles_bp
from .jobs import jobs_bp
from .applications import applications_bp
from .documents import documents_bp

__all__ = [
    "profiles_bp",
    "jobs_bp",
    "applications_bp",
    "documents_bp",
]

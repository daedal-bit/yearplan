__version__ = '0.0.0'

# Convenience re-exports for tests and simple imports
from .app import app, storage  # noqa: F401
from .storage import YearPlanStorage  # noqa: F401

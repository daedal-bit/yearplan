# Compatibility shim: expose storage from inner package for tests/imports
from .yearplan.storage import YearPlanStorage  # noqa: F401

# Compatibility shim: expose app, storage from inner package for tests/imports
from .yearplan.app import app, storage  # noqa: F401

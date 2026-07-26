"""Grade Change Intelligence REST API.

Wraps the already-validated Python modules at the repository root. No model,
feature, scoring or evaluation logic is defined in this package.
"""

__all__ = ["create_app"]

from .app import create_app  # noqa: E402

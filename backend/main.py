"""Entry point for the Grade Change Intelligence API.

    python -m uvicorn main:app --reload --port 8000     # from backend/
    python main.py                                      # equivalent
"""

from __future__ import annotations

import os

from gci_api import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        reload=bool(os.environ.get("RELOAD")),
    )

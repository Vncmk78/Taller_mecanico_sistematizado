import os
import sys

# El backend (paquete `gateway`, `shared`, etc.) vive en /backend.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from gateway.main import app  # noqa: E402

# Vercel Python detecta la variable `app` (ASGI) y la sirve.

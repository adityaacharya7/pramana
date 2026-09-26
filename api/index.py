"""Vercel entry point: the PRAMANA API as one Python function, served under
/api (vercel.json rewrites /api/* here; the React app is static).

Configuration comes from environment variables - see README "Deploying to
Vercel". The database must already be prepared from the CLI (`init-db`, or
`demo-reset --yes` for the demo build); a cold start never creates schema or
seeds data.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi import FastAPI  # noqa: E402

from pramana.main import create_app  # noqa: E402

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", create_app())

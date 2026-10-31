"""Vercel serverless entrypoint: /api/* is rewritten here (see vercel.json)."""
from backend.api import app  # noqa: F401

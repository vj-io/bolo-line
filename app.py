"""Entry point for hosts that look for a top-level app (Vercel). Docker runs server.main:app directly."""
from server.main import app  # noqa: F401

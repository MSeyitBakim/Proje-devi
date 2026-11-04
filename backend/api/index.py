"""Vercel entry point. Note: Vercel's filesystem is ephemeral, so SQLite writes do not persist."""

from app.main import app  # noqa: F401

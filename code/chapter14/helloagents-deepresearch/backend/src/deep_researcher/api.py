"""Backward-compatible API exports."""

from __future__ import annotations

from .app.api.main import app, create_app

__all__ = [
    "app",
    "create_app",
]


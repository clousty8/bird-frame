"""`GET /health` — hors `/api/v1`, sans authentification (contrat §1.12)."""

from __future__ import annotations

from fastapi import APIRouter

from app.version import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}

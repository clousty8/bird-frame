"""`GET /health` — hors `/api/v1`, sans authentification (contrat §1.12)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])

SERVER_VERSION = "0.1.0"


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": SERVER_VERSION}

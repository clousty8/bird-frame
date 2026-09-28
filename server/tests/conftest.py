from __future__ import annotations

import shutil
import struct
import wave
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

FIXTURES_SPECIES_DATA = Path(__file__).parent / "fixtures" / "species-data"
ADMIN_TOKEN = "test-admin-token-at-least-32-characters-long"
SOX_PATH = shutil.which("sox") or "/opt/homebrew/bin/sox"


@pytest.fixture
def app_settings(tmp_path: Path) -> Settings:
    return Settings(
        db_path=str(tmp_path / "bird-frame.db"),
        data_dir=str(tmp_path / "data"),
        admin_token=ADMIN_TOKEN,
        cors_origins="http://localhost:5173",
        species_data_dir=str(FIXTURES_SPECIES_DATA),
        sox_path=SOX_PATH,
        max_upload_mb=25,
        auto_migrate=True,
    )


@pytest.fixture
def client(app_settings: Settings):
    app = create_app(app_settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def registered_node(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/nodes/register",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "site_slug": "pornic",
            "site_name": "Pornic",
            "node_name": "Test node",
            "timezone": "Europe/Paris",
            "lat": 47.1155,
            "lon": -2.1046,
            "auto_main_name": False,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def auth_headers(registered_node: dict) -> dict:
    return {"Authorization": f"Bearer {registered_node['bridge_shared_secret']}"}


def utc_str(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_detection(
    node_local_id: int,
    scientific_name: str = "Erithacus rubecula",
    confidence: float = 0.9,
    minutes_ago: float = 1.0,
    has_clip: bool = False,
    clip_name: str | None = None,
    common_name: str | None = "Rougegorge familier",
    predictions: list | None = None,
) -> dict:
    when = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return {
        "node_local_id": node_local_id,
        "detected_at_utc": utc_str(when),
        "scientific_name": scientific_name,
        "common_name": common_name,
        "confidence": confidence,
        "source_id": 1,
        "source_display_name": "Sound Card 1",
        "clip_name": clip_name,
        "has_clip": has_clip,
        "predictions": predictions or [],
    }


def make_wav_bytes(duration_s: float = 0.3, sample_rate: int = 24000) -> bytes:
    """WAV mono 16 bits de silence, minimal mais valide, que sox sait traiter."""
    n_samples = int(duration_s * sample_rate)
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(struct.pack("<h", 0) for _ in range(n_samples)))
    return buf.getvalue()

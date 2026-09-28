"""`clip_paths()` — défense en profondeur contre la traversée de répertoire (constat
critique : un `scientific_name` non filtré en amont ne doit jamais pouvoir faire écrire
un fichier hors de `data_dir`, même si la validation d'ingestion (`sync_service`) était
un jour contournée ou modifiée par erreur.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingest.clip_storage import clip_paths
from app.species_data.naming import is_safe_scientific_name


def test_clip_paths_rejects_absolute_path_escape(tmp_path: Path):
    with pytest.raises(ValueError):
        clip_paths(tmp_path, "pornic", "/etc/cron.d", 1, ".wav")


def test_clip_paths_rejects_dotdot_escape(tmp_path: Path):
    with pytest.raises(ValueError):
        clip_paths(tmp_path, "pornic", "../../../../tmp/pwn", 1, ".wav")


def test_clip_paths_accepts_legitimate_scientific_name(tmp_path: Path):
    audio_path, png_path = clip_paths(tmp_path, "pornic", "Erithacus rubecula", 42, ".wav")
    assert audio_path == tmp_path / "clips" / "pornic" / "Erithacus_rubecula" / "42.wav"
    assert png_path == tmp_path / "clips" / "pornic" / "Erithacus_rubecula" / "42.png"
    assert audio_path.parent.is_dir()


def test_clip_paths_accepts_birdnet_non_taxonomic_label(tmp_path: Path):
    # « Human non-vocal », « Dog »… — étiquettes BirdNET non taxonomiques légitimes
    # (contrat, cf. app/ingest/canonical.py) : espaces et tirets doivent rester acceptés.
    audio_path, _ = clip_paths(tmp_path, "pornic", "Human non-vocal", 1, ".wav")
    assert audio_path.parent.name == "Human_non-vocal"


@pytest.mark.parametrize(
    "name",
    [
        "/etc/cron.d",
        "../../../../tmp/pwn",
        "Erithacus/rubecula",
        "Erithacus\\rubecula",
        "..",
        "",
        "123 rubecula",
    ],
)
def test_is_safe_scientific_name_rejects_unsafe(name: str):
    assert is_safe_scientific_name(name) is False


@pytest.mark.parametrize(
    "name",
    ["Erithacus rubecula", "Human non-vocal", "Dog", "Larus fuscus graellsii"],
)
def test_is_safe_scientific_name_accepts_legitimate(name: str):
    assert is_safe_scientific_name(name) is True

"""Rattrapage des alias taxonomiques sur les données déjà ingérées (contrat §1.6/§7.3) :
`app/ingest/recanonicalize.py` et `scripts/recanonicalize.py`.

Scénario réel reproduit : des détections `Coloeus monedula` ingérées AVANT que
`aliases.json` ne contienne l'alias vers `Corvus monedula` (nom de l'univers/base/).
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.ingest import canonical as canonical_module
from app.ingest.recanonicalize import AliasConflictError, recanonicalize_existing, validate_aliases
from app.main import create_app
from app.models.detection import Detection, Prediction
from app.models.kept_clip import KeptClip
from app.models.species_name import SpeciesName
from app.models.species_site_rule import SpeciesSiteRule
from app.species_data.store import load_species_data
from tests.conftest import ADMIN_TOKEN, FIXTURES_SPECIES_DATA, make_detection

ALIASES = {"Coloeus monedula": "Corvus monedula"}


@pytest.fixture
def species_data_without_aliases(tmp_path: Path) -> Path:
    target = tmp_path / "species-data"
    shutil.copytree(FIXTURES_SPECIES_DATA, target)
    (target / "aliases.json").unlink()
    return target


@pytest.fixture
def client_before_alias(app_settings: Settings, species_data_without_aliases: Path):
    settings = app_settings.model_copy(update={"species_data_dir": str(species_data_without_aliases)})
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _register(client: TestClient) -> tuple[int, dict]:
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
    body = resp.json()
    return body["node_id"], {"Authorization": f"Bearer {body['bridge_shared_secret']}"}


def _sync(client: TestClient, node_id: int, headers: dict, detections: list[dict], since_id: int = 0) -> dict:
    node_max = max(d["node_local_id"] for d in detections)
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=headers,
        json={"since_id": since_id, "node_max_id": node_max, "detections": detections},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _session(client: TestClient):
    return client.app.state.session_local()


def test_validate_aliases_refuse_chains_and_self_alias():
    validate_aliases(ALIASES)
    with pytest.raises(ValueError, match="chaîne"):
        validate_aliases({"A a": "B b", "B b": "C c"})
    with pytest.raises(ValueError, match="lui-même"):
        validate_aliases({"A a": "A a"})


def test_loader_ignores_chained_alias(tmp_path: Path, species_data_without_aliases: Path):
    (species_data_without_aliases / "aliases.json").write_text(
        json.dumps({"Coloeus monedula": "Corvus monedula", "X y": "Coloeus monedula"}), encoding="utf-8"
    )
    store = load_species_data(species_data_without_aliases)
    assert store.aliases == {"Coloeus monedula": "Corvus monedula"}
    assert [f.file for f in store.invalid_files] == ["aliases.json"]


def test_recanonicalize_renames_existing_rows_and_keeps_raw_name(client_before_alias: TestClient):
    client = client_before_alias
    node_id, headers = _register(client)
    detections = [
        make_detection(
            i,
            scientific_name="Coloeus monedula",
            common_name="Choucas des tours",
            confidence=0.5 + i / 100,
            has_clip=True,
            clip_name=f"2026/09/c{i}.wav",
            predictions=[{"scientific_name": "Coloeus monedula", "common_name": "Choucas des tours", "confidence": 0.1}]
            if i == 1
            else [],
        )
        for i in range(1, 4)
    ] + [
        make_detection(
            i,
            scientific_name="Corvus monedula",
            common_name="Choucas des tours",
            confidence=0.9 + i / 100,
            has_clip=True,
            clip_name=f"2026/09/k{i}.wav",
        )
        for i in range(4, 7)
    ]
    _sync(client, node_id, headers, detections)

    # Avant le rattrapage : deux « espèces » pour le même oiseau.
    names = {s["scientific_name"] for s in client.get("/api/v1/sites/pornic/species").json()["species"]}
    assert {"Coloeus monedula", "Corvus monedula"} <= names

    db = _session(client)
    try:
        report = recanonicalize_existing(db, ALIASES)
    finally:
        db.close()
    assert report.detections == 3
    assert report.predictions == 1
    assert report.kept_clips == 3
    assert report.species_names_merged == 1  # Corvus monedula déjà en cache
    assert report.recomputed == [(1, "Corvus monedula")]

    db = _session(client)
    try:
        rows = db.query(Detection).order_by(Detection.node_local_id).all()
        assert {d.scientific_name for d in rows} == {"Corvus monedula"}
        # Le nom brut reçu est conservé pour l'audit (contrat §9.1).
        assert [d.raw_scientific_name for d in rows[:3]] == ["Coloeus monedula"] * 3
        assert db.query(Prediction).filter(Prediction.scientific_name == "Coloeus monedula").count() == 0
        assert db.get(SpeciesName, "Coloeus monedula") is None
        assert db.get(SpeciesName, "Corvus monedula").common_name_fr == "Choucas des tours"
        # Top-5 recalculé sur l'union : 6 candidats → 5 actifs, le moins bon évincé.
        active = (
            db.query(KeptClip)
            .filter(KeptClip.scientific_name == "Corvus monedula", KeptClip.evicted_at.is_(None))
            .all()
        )
        assert len(active) == 5
        assert db.query(KeptClip).filter(KeptClip.scientific_name == "Coloeus monedula").count() == 0
        worst = db.query(Detection).filter(Detection.node_local_id == 1).one()
        assert worst.id not in {row.detection_id for row in active}
    finally:
        db.close()

    names = {s["scientific_name"] for s in client.get("/api/v1/sites/pornic/species").json()["species"]}
    assert "Coloeus monedula" not in names
    assert "Corvus monedula" in names

    # Idempotent : relancé, plus rien à renommer.
    db = _session(client)
    try:
        again = recanonicalize_existing(db, ALIASES)
    finally:
        db.close()
    assert again.renamed_rows == 0


def test_recanonicalize_refuses_conflicting_rules_without_changing_anything(client_before_alias: TestClient):
    client = client_before_alias
    node_id, headers = _register(client)
    _sync(client, node_id, headers, [make_detection(1, scientific_name="Coloeus monedula", common_name=None)])
    db = _session(client)
    try:
        for name in ("Coloeus monedula", "Corvus monedula"):
            db.add(SpeciesSiteRule(site_id=1, scientific_name=name, rule="impossible"))
        db.commit()
        with pytest.raises(AliasConflictError):
            recanonicalize_existing(db, ALIASES)
        db.rollback()
        assert db.query(Detection).one().scientific_name == "Coloeus monedula"
    finally:
        db.close()


def test_sync_warns_once_per_species_absent_from_universe_and_base(
    client: TestClient, registered_node: dict, auth_headers: dict, caplog: pytest.LogCaptureFixture
):
    canonical_module._warned_unknown_names.discard("Pica pica")
    node_id = registered_node["node_id"]
    with caplog.at_level(logging.WARNING, logger="bird_frame.species_data"):
        _sync(client, node_id, auth_headers, [make_detection(1, scientific_name="Pica pica", common_name=None)])
        _sync(
            client,
            node_id,
            auth_headers,
            [make_detection(2, scientific_name="Pica pica", common_name=None), make_detection(3)],
            since_id=1,
        )
    messages = [r.getMessage() for r in caplog.records if "absente de l'univers" in r.getMessage()]
    assert messages == ["espèce ingérée absente de l'univers et de base/ : 'Pica pica' — si c'est un synonyme, l'ajouter à species-data/aliases.json (contrat §7.3)"]


def test_script_applies_aliases_to_a_database(
    client_before_alias: TestClient, app_settings: Settings, capsys: pytest.CaptureFixture
):
    from scripts.recanonicalize import main

    client = client_before_alias
    node_id, headers = _register(client)
    _sync(client, node_id, headers, [make_detection(1, scientific_name="Coloeus monedula", common_name=None)])

    assert main(["--db", app_settings.db_path, "--species-data", str(FIXTURES_SPECIES_DATA), "--dry-run"]) == 0
    assert "Coloeus monedula → Corvus monedula" in capsys.readouterr().out
    db = _session(client)
    try:
        assert db.query(Detection).one().scientific_name == "Coloeus monedula"
    finally:
        db.close()

    assert main(["--db", app_settings.db_path, "--species-data", str(FIXTURES_SPECIES_DATA)]) == 0
    assert "detections=1" in capsys.readouterr().out
    db = _session(client)
    try:
        assert db.query(Detection).one().scientific_name == "Corvus monedula"
    finally:
        db.close()

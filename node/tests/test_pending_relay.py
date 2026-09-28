"""WP-06 : parseur SSE sur un flux simulé + traduction vers le format du contrat (§4.5)."""

from __future__ import annotations

import json

import pytest

from bridge.pending_relay import build_pending_items
from bridge.sse import iter_sse_events


async def _lines(items: list[str]):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_iter_sse_events_parses_event_and_data() -> None:
    raw = [
        "event: pending",
        'data: [{"a": 1}]',
        "",
        "event: heartbeat",
        "data: {}",
        "",
    ]
    events = [event async for event in iter_sse_events(_lines(raw))]
    assert events == [("pending", '[{"a": 1}]'), ("heartbeat", "{}")]


@pytest.mark.asyncio
async def test_iter_sse_events_ignores_comments_and_unknown_fields() -> None:
    raw = [
        ": ceci est un commentaire keep-alive",
        "retry: 3000",
        "id: 42",
        "event: pending",
        "data: []",
        "",
    ]
    events = [event async for event in iter_sse_events(_lines(raw))]
    assert events == [("pending", "[]")]


@pytest.mark.asyncio
async def test_iter_sse_events_joins_multiline_data() -> None:
    raw = ["event: pending", "data: line1", "data: line2", ""]
    events = [event async for event in iter_sse_events(_lines(raw))]
    assert events == [("pending", "line1\nline2")]


def test_build_pending_items_maps_fields_from_birdnet_go_dto() -> None:
    raw_items = [
        {
            "species": "Rougegorge familier",
            "scientificName": "Erithacus rubecula",
            "thumbnail": "http://localhost:8080/should/not/be/relayed.jpg",
            "status": "active",
            "firstDetected": 1790519938,
            "lastUpdated": 1790519944,
            "source": "Sound Card 1",
            "sourceID": "audio_card_881db84a",
            "hitCount": 3,
        }
    ]
    items = build_pending_items(raw_items)
    assert items == [
        {
            "scientific_name": "Erithacus rubecula",
            "common_name": "Rougegorge familier",
            "status": "active",
            "hit_count": 3,
            "confidence_hint": None,
            "first_detected_unix": 1790519938,
            "last_updated_unix": 1790519944,
            "source_id": "audio_card_881db84a",
        }
    ]
    assert "thumbnail" not in json.dumps(items)  # jamais relayé


def test_build_pending_items_confidence_hint_from_model_contributions() -> None:
    raw_items = [
        {
            "species": None,
            "scientificName": "Turdus merula",
            "status": "active",
            "firstDetected": 1,
            "lastUpdated": 2,
            "sourceID": None,
            "hitCount": 5,
            "modelContributions": [
                {"modelID": "birdnet", "hitCount": 3, "maxConfidence": 0.4},
                {"modelID": "other", "hitCount": 2, "maxConfidence": 0.7},
            ],
        }
    ]
    items = build_pending_items(raw_items)
    assert items[0]["confidence_hint"] == pytest.approx(0.7)
    assert items[0]["common_name"] is None


def test_build_pending_items_empty_list() -> None:
    assert build_pending_items([]) == []


def test_build_pending_items_raises_on_missing_required_field() -> None:
    """`build_pending_items` indexe directement les champs requis (pas de `.get()`) : un item
    incomplet doit lever une KeyError franche plutôt qu'être mal traduit en silence. C'est à
    `_consume_sse` (testé en intégration) d'attraper cette exception pour ne jamais mourir sur un
    item mal formé."""
    raw_items = [
        {
            "species": "Rougegorge familier",
            "scientificName": "Erithacus rubecula",
            # "status" manquant : version future de BirdNET-Go, item pas encore typé, etc.
            "firstDetected": 1,
            "lastUpdated": 2,
        }
    ]
    with pytest.raises(KeyError):
        build_pending_items(raw_items)

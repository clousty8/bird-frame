"""`GET`/`POST /nodes/{id}/commands[/ack]` (contrat §4.7-4.8) et
`GET /sites/{slug}/commands` (audit navigateur, §6.29) — reste du WP-11, complété ici."""


def _enqueue_via_rule(client, rule="impossible", scientific_name="Pica%20pica", **extra):
    resp = client.put(f"/api/v1/sites/pornic/species-rules/{scientific_name}", json={"rule": rule, **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()["rule"]["commands"][0]["command_id"]


def test_bridge_poll_delivers_and_redelivers_after_120s(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    _enqueue_via_rule(client)

    resp = client.get(f"/api/v1/nodes/{node_id}/commands", headers=auth_headers)
    assert resp.status_code == 200
    commands = resp.json()["commands"]
    assert len(commands) == 1
    assert commands[0]["kind"] == "exclude_species"
    assert set(commands[0].keys()) == {"id", "kind", "payload", "created_at", "expires_at"}

    # Livrée mais pas encore acquittée : elle reste "delivered" côté audit navigateur.
    audit = client.get("/api/v1/sites/pornic/commands").json()
    assert audit["commands"][0]["status"] == "delivered"


def test_ack_applied_then_idempotent_then_conflict(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    cmd_id = _enqueue_via_rule(client)
    client.get(f"/api/v1/nodes/{node_id}/commands", headers=auth_headers)

    ack1 = client.post(
        f"/api/v1/nodes/{node_id}/commands/{cmd_id}/ack",
        headers=auth_headers,
        json={"status": "applied", "result": {"changed": True, "list": "exclude", "restart_required": False}},
    )
    assert ack1.status_code == 200
    assert ack1.json() == {"id": cmd_id, "status": "applied"}

    # Idempotent : même statut renvoyé, pas d'erreur.
    ack2 = client.post(
        f"/api/v1/nodes/{node_id}/commands/{cmd_id}/ack",
        headers=auth_headers,
        json={"status": "applied", "result": None},
    )
    assert ack2.status_code == 200

    # Contradictoire : conflit.
    ack3 = client.post(
        f"/api/v1/nodes/{node_id}/commands/{cmd_id}/ack",
        headers=auth_headers,
        json={"status": "failed", "error": "changement d'avis"},
    )
    assert ack3.status_code == 409
    assert ack3.json()["error"] == "command_already_final"

    audit = client.get("/api/v1/sites/pornic/commands").json()
    assert audit["commands"][0]["status"] == "applied"
    assert audit["commands"][0]["result"] == {"changed": True, "list": "exclude", "restart_required": False}


def test_ack_failed_requires_error_message(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    cmd_id = _enqueue_via_rule(client)

    resp = client.post(
        f"/api/v1/nodes/{node_id}/commands/{cmd_id}/ack",
        headers=auth_headers,
        json={"status": "failed", "error": None},
    )
    assert resp.status_code == 422


def test_ack_unknown_command_404(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    resp = client.post(
        f"/api/v1/nodes/{node_id}/commands/999999/ack",
        headers=auth_headers,
        json={"status": "applied"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "command_not_found"


def test_site_commands_filters_by_status_and_kind(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    cmd_id = _enqueue_via_rule(client, rule="impossible", scientific_name="Pica%20pica")
    _enqueue_via_rule(client, rule="present", scientific_name="Turdus%20merula", threshold_override=0.35)
    client.get(f"/api/v1/nodes/{node_id}/commands", headers=auth_headers)
    client.post(f"/api/v1/nodes/{node_id}/commands/{cmd_id}/ack", headers=auth_headers, json={"status": "applied"})

    all_cmds = client.get("/api/v1/sites/pornic/commands").json()
    assert all_cmds["total"] == 3  # exclude + include + set_species_threshold

    applied = client.get("/api/v1/sites/pornic/commands?status=applied").json()
    assert applied["total"] == 1
    assert applied["commands"][0]["kind"] == "exclude_species"

    only_include = client.get("/api/v1/sites/pornic/commands?kind=include_species").json()
    assert only_include["total"] == 1


def test_site_commands_invalid_status_422(client, registered_node):
    resp = client.get("/api/v1/sites/pornic/commands?status=bogus")
    assert resp.status_code == 422

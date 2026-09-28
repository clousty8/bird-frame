"""WP-12 : `GET`/`PUT`/`DELETE /sites/{slug}/species-rules` — contrat §6.20 à §6.22."""

import threading
import time

from tests.conftest import make_detection


def test_put_present_rule_creates_include_and_threshold_commands(client, registered_node, auth_headers):
    resp = client.put(
        "/api/v1/sites/pornic/species-rules/Larus%20argentatus",
        json={"rule": "present", "threshold_override": 0.4, "reason": "Nicheur ici"},
    )
    assert resp.status_code == 200, resp.text
    rule = resp.json()["rule"]
    assert rule["scientific_name"] == "Larus argentatus"
    assert rule["rule"] == "present"
    assert rule["threshold_override"] == 0.4
    assert rule["sync_status"] == "pending"

    # Ordre imposé par le contrat §5.4 (étape 3 avant étape 4) : le seuil avant l'inclusion.
    kinds = [c["kind"] for c in rule["commands"]]
    assert kinds == ["set_species_threshold", "include_species"]
    for c in rule["commands"]:
        assert c["payload"]["scientific_name"] == "Larus argentatus"
        assert c["status"] == "pending"

    # Persistant : un GET plus tard retrouve les mêmes commandes (contrat §6.20).
    listed = client.get("/api/v1/sites/pornic/species-rules").json()
    assert len(listed["rules"]) == 1
    assert [c["kind"] for c in listed["rules"][0]["commands"]] == ["set_species_threshold", "include_species"]

    node_id = registered_node["node_id"]
    commands = client.get(f"/api/v1/nodes/{node_id}/commands", headers=auth_headers).json()["commands"]
    assert {c["kind"] for c in commands} == {"include_species", "set_species_threshold"}


def test_put_impossible_rule_creates_exclude_command(client, registered_node):
    resp = client.put(
        "/api/v1/sites/pornic/species-rules/Columba%20livia", json={"rule": "impossible", "reason": "Confusion"}
    )
    assert resp.status_code == 200
    rule = resp.json()["rule"]
    assert [c["kind"] for c in rule["commands"]] == ["exclude_species"]


def test_put_redirect_rule_creates_no_command_and_recomputes_existing_detections(
    client, registered_node, auth_headers
):
    node_id = registered_node["node_id"]
    det = make_detection(1, scientific_name="Coloeus monedula", common_name=None)
    resp = client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    assert resp.status_code == 200, resp.text

    # `Coloeus monedula` est aliasé vers `Corvus monedula` (contrat §1.6), donc c'est ce
    # nom canonique qui porte la règle.
    resp = client.put(
        "/api/v1/sites/pornic/species-rules/Corvus%20monedula",
        json={"rule": "redirect", "redirect_to_scientific_name": "Turdus merula", "reason": "test"},
    )
    assert resp.status_code == 200, resp.text
    rule = resp.json()["rule"]
    assert rule["rule"] == "redirect"
    assert rule["redirect_to_scientific_name"] == "Turdus merula"
    assert rule["commands"] == []  # aucun mécanisme natif pour une redirection

    detections = client.get("/api/v1/sites/pornic/detections").json()["detections"]
    assert len(detections) == 1
    assert detections[0]["scientific_name"] == "Corvus monedula"
    assert detections[0]["effective_scientific_name"] == "Turdus merula"

    # Rattrapage inverse : supprimer la règle remet `redirected_to_scientific_name` à NULL.
    resp = client.delete("/api/v1/sites/pornic/species-rules/Corvus%20monedula")
    assert resp.status_code == 200
    detections = client.get("/api/v1/sites/pornic/detections").json()["detections"]
    assert detections[0]["effective_scientific_name"] == "Corvus monedula"


def test_redirect_chain_conflicts(client, registered_node):
    client.put(
        "/api/v1/sites/pornic/species-rules/Pica%20pica",
        json={"rule": "redirect", "redirect_to_scientific_name": "Corvus corone"},
    )

    # La cible (Pica pica) redirige déjà elle-même : chaîne interdite.
    resp = client.put(
        "/api/v1/sites/pornic/species-rules/Garrulus%20glandarius",
        json={"rule": "redirect", "redirect_to_scientific_name": "Pica pica"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "redirect_chain"

    # La source (Corvus corone) est déjà la cible d'une redirection : chaîne interdite.
    resp = client.put(
        "/api/v1/sites/pornic/species-rules/Corvus%20corone",
        json={"rule": "redirect", "redirect_to_scientific_name": "Turdus merula"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "redirect_chain"


def test_concurrent_redirect_puts_do_not_create_a_cross_chain(client, registered_node, monkeypatch):
    """Deux PUT concurrents A→B et B→A ne doivent jamais aboutir tous les deux —
    `_rules_write_lock` doit sérialiser le contrôle anti-chaîne et l'écriture, y compris
    entre deux requêtes distinctes (donc deux sessions DB distinctes)."""
    import app.api.species_rules as species_rules_module

    real_check = species_rules_module._check_redirect_chain

    def widened_check(db, site_id, source, target):
        result = real_check(db, site_id, source, target)
        # Élargit la fenêtre entre le contrôle et l'écriture pour rendre la course
        # déterministe si le verrou ne protégeait pas cette section — avec le verrou,
        # ce sleep a lieu à l'intérieur de la section critique et ne change rien à
        # l'issue (l'autre thread reste bloqué sur l'acquisition du verrou).
        time.sleep(0.05)
        return result

    monkeypatch.setattr(species_rules_module, "_check_redirect_chain", widened_check)

    start = threading.Event()
    results: dict[str, object] = {}

    def put_a_to_b():
        start.wait(timeout=5)
        results["a"] = client.put(
            "/api/v1/sites/pornic/species-rules/Pica%20pica",
            json={"rule": "redirect", "redirect_to_scientific_name": "Corvus corone"},
        )

    def put_b_to_a():
        start.wait(timeout=5)
        results["b"] = client.put(
            "/api/v1/sites/pornic/species-rules/Corvus%20corone",
            json={"rule": "redirect", "redirect_to_scientific_name": "Pica pica"},
        )

    t1 = threading.Thread(target=put_a_to_b)
    t2 = threading.Thread(target=put_b_to_a)
    t1.start()
    t2.start()
    start.set()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert "a" in results and "b" in results, "une des deux requêtes n'a pas abouti à temps"
    statuses = sorted([results["a"].status_code, results["b"].status_code])
    assert statuses == [200, 409], (
        results["a"].status_code,
        results["a"].text,
        results["b"].status_code,
        results["b"].text,
    )

    rules = client.get("/api/v1/sites/pornic/species-rules").json()["rules"]
    redirect_pairs = {
        (r["scientific_name"], r["redirect_to_scientific_name"]) for r in rules if r["rule"] == "redirect"
    }
    assert len(redirect_pairs) == 1, f"chaîne croisée créée : {redirect_pairs}"


def test_self_redirect_rejected(client, registered_node):
    resp = client.put(
        "/api/v1/sites/pornic/species-rules/Turdus%20merula",
        json={"rule": "redirect", "redirect_to_scientific_name": "Turdus merula"},
    )
    assert resp.status_code == 422


def test_present_rule_forbids_redirect_target(client, registered_node):
    resp = client.put(
        "/api/v1/sites/pornic/species-rules/Turdus%20merula",
        json={"rule": "present", "redirect_to_scientific_name": "Erithacus rubecula"},
    )
    assert resp.status_code == 422


def test_redirect_rule_requires_target(client, registered_node):
    resp = client.put("/api/v1/sites/pornic/species-rules/Turdus%20merula", json={"rule": "redirect"})
    assert resp.status_code == 422


def test_retry_after_failed_reemits_full_application(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    resp = client.put(
        "/api/v1/sites/pornic/species-rules/Pica%20pica", json={"rule": "impossible"}
    )
    cmd_id = resp.json()["rule"]["commands"][0]["command_id"]

    # Le bridge signale un échec permanent.
    ack = client.post(
        f"/api/v1/nodes/{node_id}/commands/{cmd_id}/ack",
        headers=auth_headers,
        json={"status": "failed", "error": "espèce introuvable côté nœud"},
    )
    assert ack.status_code == 200

    listed = client.get("/api/v1/sites/pornic/species-rules").json()["rules"][0]
    assert listed["sync_status"] == "failed"

    # Bouton « réessayer » : ré-enregistrer la même règle ré-émet la commande (A = N).
    resp = client.put("/api/v1/sites/pornic/species-rules/Pica%20pica", json={"rule": "impossible"})
    assert resp.status_code == 200
    rule = resp.json()["rule"]
    assert [c["kind"] for c in rule["commands"]] == ["exclude_species"]
    assert rule["sync_status"] == "pending"


def test_delete_unknown_rule_404(client, registered_node):
    resp = client.delete("/api/v1/sites/pornic/species-rules/Nowhereus%20birdus")
    assert resp.status_code == 404
    assert resp.json()["error"] == "rule_not_found"


def test_site_species_list_exposes_rule_field(client, registered_node, auth_headers):
    node_id = registered_node["node_id"]
    det = make_detection(1, scientific_name="Columba livia", common_name="Pigeon biset")
    client.post(
        f"/api/v1/nodes/{node_id}/sync",
        headers=auth_headers,
        json={"since_id": 0, "node_max_id": 1, "detections": [det]},
    )
    client.put("/api/v1/sites/pornic/species-rules/Columba%20livia", json={"rule": "impossible"})

    species = client.get("/api/v1/sites/pornic/species").json()["species"]
    entry = next(s for s in species if s["scientific_name"] == "Columba livia")
    # « impossible → affichage tel quel mais marqué » (consigne) : la détection brute
    # reste listée, seul le champ `rule` la signale.
    assert entry["rule"] == "impossible"

    # La vue effective (calendrier), elle, l'exclut bien.
    calendar = client.get("/api/v1/sites/pornic/calendar").json()
    assert calendar["species"] == []

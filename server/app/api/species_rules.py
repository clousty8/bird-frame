"""Routes `/sites/{slug}/species-rules` — contrat §6.20 à §6.22 (WP-12).

`_create_rule_commands` tague chaque commande créée d'un `origin_batch` (uuid4) commun
au PUT/DELETE en cours, et `SpeciesSiteRule.last_command_batch` retient celui du dernier
PUT — c'est ce qui permet à `GET /species-rules` de retrouver, même plus tard, « les
commandes créées par le dernier PUT de cette règle » (contrat §6.20). Un simple
rapprochement par `created_at` (précision à la seconde, imposée par le contrat §1.3)
serait fragile : deux PUT rapprochés (moins d'une seconde d'écart) fusionneraient leurs
lots de commandes à tort — voir `decisions_outside_contract` dans le rapport de ce lot.
"""

from __future__ import annotations

import json
import threading
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.common_lookups import get_site_or_404
from app.deps import get_db, get_species_data
from app.errors import ApiError
from app.ingest.canonical import aliases_for
from app.ingest.commands import serialize_command_info
from app.ingest.redirect_recompute import recompute_redirect_for_site_species
from app.ingest.rule_commands import compute_rule_commands
from app.live.compute import resolve_common_name_fr
from app.models.node import Node
from app.models.node_command import NodeCommand
from app.models.species_site_rule import SpeciesSiteRule
from app.schemas.species_rules import PutSpeciesRuleBody
from app.species_data.store import SpeciesDataStore
from app.time_utils import utc_now_str

router = APIRouter(tags=["species-rules"])

# `_check_redirect_chain` (lire) puis l'écriture de la règle (`put_species_rule`) sont
# deux opérations séparées, chacune dans sa propre transaction/session (une par
# requête) : sans verrou, deux PUT concurrents (ex. deux onglets navigateur) peuvent
# chacun passer le contrôle avant que l'autre n'ait committé, et créer une chaîne
# croisée A→B / B→A que ce contrôle est censé interdire (409 `redirect_chain`). Un seul
# process uvicorn (pas de workers, contrat de déploiement S1) exécute les routes
# synchrones dans un threadpool : un verrou en mémoire du process suffit à sérialiser
# ces écritures, peu fréquentes (admin), sans coût perceptible.
_rules_write_lock = threading.Lock()


def _canonicalize(raw: str, store: SpeciesDataStore) -> str:
    return store.resolve_reference(raw) or raw.strip().replace("_", " ")


def _rule_query(db: Session, site_id: int, scientific_name: str):
    return db.query(SpeciesSiteRule).filter(
        SpeciesSiteRule.site_id == site_id, SpeciesSiteRule.scientific_name == scientific_name
    )


def _last_put_commands(db: Session, rule: SpeciesSiteRule) -> list[NodeCommand]:
    if rule.last_command_batch is None:
        return []
    return (
        db.query(NodeCommand)
        .filter(
            NodeCommand.origin_type == "species_rule",
            NodeCommand.origin_id == rule.id,
            NodeCommand.origin_batch == rule.last_command_batch,
        )
        .order_by(NodeCommand.id.asc())
        .all()
    )


def _sync_status(commands: list[NodeCommand]) -> str:
    if not commands:
        return "none"
    statuses = {c.status for c in commands}
    if statuses & {"failed", "expired"}:
        return "failed"
    if statuses & {"pending", "delivered"}:
        return "pending"
    return "applied"


def _rule_out(db: Session, store: SpeciesDataStore, rule: SpeciesSiteRule) -> dict:
    commands = _last_put_commands(db, rule)
    redirect_target = rule.redirect_to_scientific_name if rule.rule == "redirect" else None
    return {
        "scientific_name": rule.scientific_name,
        "common_name_fr": resolve_common_name_fr(rule.scientific_name, store, db),
        "rule": rule.rule,
        "threshold_override": rule.threshold_override if rule.rule == "present" else None,
        "redirect_to_scientific_name": redirect_target,
        "redirect_to_common_name_fr": (
            resolve_common_name_fr(redirect_target, store, db) if redirect_target else None
        ),
        "reason": rule.reason,
        "updated_at": rule.updated_at,
        "sync_status": _sync_status(commands),
        "commands": [serialize_command_info(c) for c in commands],
    }


@router.get("/sites/{slug}/species-rules")
def list_species_rules(
    slug: str, db: Session = Depends(get_db), store: SpeciesDataStore = Depends(get_species_data)
) -> dict:
    site = get_site_or_404(db, slug)
    rules = (
        db.query(SpeciesSiteRule)
        .filter(SpeciesSiteRule.site_id == site.id)
        .order_by(SpeciesSiteRule.updated_at.desc())
        .all()
    )
    return {"site_slug": site.slug, "rules": [_rule_out(db, store, r) for r in rules]}


def _validate_rule_body(body: PutSpeciesRuleBody) -> None:
    if body.rule == "present":
        if body.threshold_override is not None and not (0.01 <= body.threshold_override <= 1.0):
            raise ApiError(422, "validation_error", "threshold_override doit être entre 0.01 et 1.0.")
        if body.redirect_to_scientific_name is not None:
            raise ApiError(
                422, "validation_error", "redirect_to_scientific_name n'est autorisé que pour rule=redirect."
            )
    elif body.rule == "impossible":
        if body.threshold_override is not None:
            raise ApiError(422, "validation_error", "threshold_override n'est autorisé que pour rule=present.")
        if body.redirect_to_scientific_name is not None:
            raise ApiError(
                422, "validation_error", "redirect_to_scientific_name n'est autorisé que pour rule=redirect."
            )
    else:  # redirect
        if body.threshold_override is not None:
            raise ApiError(422, "validation_error", "threshold_override n'est autorisé que pour rule=present.")
        if not body.redirect_to_scientific_name:
            raise ApiError(422, "validation_error", "redirect_to_scientific_name est requis pour rule=redirect.")


def _check_redirect_chain(db: Session, site_id: int, source: str, target: str) -> None:
    target_redirects_elsewhere = (
        _rule_query(db, site_id, target).filter(SpeciesSiteRule.rule == "redirect").first()
    )
    if target_redirects_elsewhere:
        raise ApiError(
            409, "redirect_chain", f"« {target} » redirige déjà lui-même vers une autre espèce sur ce site."
        )
    source_is_already_a_target = (
        db.query(SpeciesSiteRule.id)
        .filter(
            SpeciesSiteRule.site_id == site_id,
            SpeciesSiteRule.rule == "redirect",
            SpeciesSiteRule.redirect_to_scientific_name == source,
        )
        .first()
    )
    if source_is_already_a_target:
        raise ApiError(409, "redirect_chain", f"« {source} » est déjà la cible d'une redirection sur ce site.")


def _create_rule_commands(
    db: Session,
    store: SpeciesDataStore,
    site_id: int,
    canonical: str,
    old_rule: str | None,
    old_threshold: float | None,
    new_rule: str | None,
    new_threshold: float | None,
    rule_id: int,
    batch_key: str,
) -> list[NodeCommand]:
    steps = compute_rule_commands(old_rule, old_threshold, new_rule, new_threshold)
    if not steps:
        return []
    nodes = db.query(Node).filter(Node.site_id == site_id, Node.decommissioned_at.is_(None)).all()
    aliases = aliases_for(canonical, store.aliases)
    created: list[NodeCommand] = []
    for node in nodes:
        for kind, extra in steps:
            payload = {"scientific_name": canonical, "aliases": aliases, **extra}
            cmd = NodeCommand(
                node_id=node.id,
                kind=kind,
                payload_json=json.dumps(payload, ensure_ascii=False),
                status="pending",
                origin_type="species_rule",
                origin_id=rule_id,
                origin_batch=batch_key,
            )
            db.add(cmd)
            created.append(cmd)
    db.flush()
    return created


@router.put("/sites/{slug}/species-rules/{scientific_name}")
def put_species_rule(
    slug: str,
    scientific_name: str,
    body: PutSpeciesRuleBody,
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    canonical = _canonicalize(scientific_name, store)
    _validate_rule_body(body)

    redirect_target: str | None = None
    if body.rule == "redirect":
        redirect_target = _canonicalize(body.redirect_to_scientific_name, store)  # type: ignore[arg-type]
        if redirect_target == canonical:
            raise ApiError(422, "validation_error", "Une espèce ne peut pas se rediriger vers elle-même.")

    # Verrouillé du contrôle anti-chaîne jusqu'au commit inclus : lecture puis écriture
    # doivent être atomiques vis-à-vis d'un autre PUT concurrent (voir _rules_write_lock).
    with _rules_write_lock:
        if body.rule == "redirect":
            _check_redirect_chain(db, site.id, canonical, redirect_target)

        row = _rule_query(db, site.id, canonical).first()
        old_rule_kind = row.rule if row else None
        old_threshold = row.threshold_override if row else None

        if row is None:
            row = SpeciesSiteRule(site_id=site.id, scientific_name=canonical, rule=body.rule)
            db.add(row)
            db.flush()

        batch_key = uuid.uuid4().hex

        row.rule = body.rule
        row.threshold_override = body.threshold_override if body.rule == "present" else None
        row.redirect_to_scientific_name = redirect_target
        row.reason = body.reason
        row.updated_at = utc_now_str()
        row.last_command_batch = batch_key

        # Effet 2 (contrat §6.21) : rattrapage sur les détections déjà en base.
        recompute_redirect_for_site_species(db, site.id, canonical, redirect_target)

        # Effet 3 : commandes §5.4.
        _create_rule_commands(
            db, store, site.id, canonical, old_rule_kind, old_threshold, body.rule, body.threshold_override, row.id, batch_key
        )

        db.commit()

    return {"rule": _rule_out(db, store, row)}


@router.delete("/sites/{slug}/species-rules/{scientific_name}")
def delete_species_rule(
    slug: str,
    scientific_name: str,
    db: Session = Depends(get_db),
    store: SpeciesDataStore = Depends(get_species_data),
) -> dict:
    site = get_site_or_404(db, slug)
    canonical = _canonicalize(scientific_name, store)

    with _rules_write_lock:
        row = _rule_query(db, site.id, canonical).first()
        if row is None:
            raise ApiError(404, "rule_not_found", f"Aucune règle pour « {canonical} » sur ce site.")

        old_rule_kind, old_threshold, rule_id = row.rule, row.threshold_override, row.id
        batch_key = uuid.uuid4().hex

        recompute_redirect_for_site_species(db, site.id, canonical, None)
        created = _create_rule_commands(
            db, store, site.id, canonical, old_rule_kind, old_threshold, None, None, rule_id, batch_key
        )

        db.delete(row)
        db.commit()

    return {"deleted": True, "commands": [serialize_command_info(c) for c in created]}

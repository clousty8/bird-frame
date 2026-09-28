"""Algorithme « règle d'espèce → commandes » — contrat §5.4.

Traduit une règle `species_site_rules` (ancienne / nouvelle) en la liste ordonnée de
commandes `node_commands` à créer, sans connaître les nœuds ni les alias : la fonction
est pure et testable isolément. L'appelant (`app/api/species_rules.py`) boucle sur les
nœuds du site et complète chaque commande avec `scientific_name`/`aliases`.
"""

from __future__ import annotations


def _desired_state(rule: str | None, threshold: float | None) -> dict:
    """État cible du nœud pour une règle — contrat §5.4.

    `D(present)` = inclus, non exclu, seuil = `threshold_override`.
    `D(impossible)` = exclu, non inclus, pas de seuil personnalisé.
    `D(redirect)` = `D(aucune règle)` : la redirection est un remappage d'affichage
    serveur uniquement, sans effet côté nœud.
    """
    if rule == "present":
        return {"inclus": True, "exclu": False, "seuil": threshold}
    if rule == "impossible":
        return {"inclus": False, "exclu": True, "seuil": None}
    return {"inclus": False, "exclu": False, "seuil": None}


def compute_rule_commands(
    old_rule: str | None,
    old_threshold: float | None,
    new_rule: str | None,
    new_threshold: float | None,
) -> list[tuple[str, dict]]:
    """Renvoie `[(kind, payload_partiel), ...]` dans l'ordre à créer (contrat §5.4).

    `payload_partiel` ne contient que les clés propres au `kind` au-delà de
    `scientific_name`/`aliases` (ex. `{"threshold": 0.4}`), que l'appelant complète.

    Cas `A = N` (ré-enregistrement à l'identique, ex. bouton « réessayer » après un
    `failed`) : ré-émet l'application complète de `N` plutôt qu'un diff vide.
    """
    old_state = _desired_state(old_rule, old_threshold)
    new_state = _desired_state(new_rule, new_threshold)

    if old_state == new_state:
        if new_rule == "present":
            commands: list[tuple[str, dict]] = [("include_species", {})]
            if new_threshold is not None:
                commands.append(("set_species_threshold", {"threshold": new_threshold}))
            return commands
        if new_rule == "impossible":
            return [("exclude_species", {})]
        return []  # redirect, ou aucune règle des deux côtés : rien à faire

    commands = []
    if old_state["exclu"] and not new_state["exclu"]:
        commands.append(("unexclude_species", {}))
    if old_state["inclus"] and not new_state["inclus"]:
        commands.append(("uninclude_species", {}))
    if old_state["seuil"] != new_state["seuil"]:
        commands.append(("set_species_threshold", {"threshold": new_state["seuil"]}))
    if new_state["inclus"] and not old_state["inclus"]:
        commands.append(("include_species", {}))
    if new_state["exclu"] and not old_state["exclu"]:
        commands.append(("exclude_species", {}))
    return commands

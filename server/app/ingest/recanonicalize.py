"""Rattrapage des alias taxonomiques sur les données DÉJÀ ingérées — contrat §1.6 / §7.3.

La canonicalisation (`aliases.json`) s'applique à l'ingestion ; une détection reçue avant
qu'un alias ne soit ajouté garde donc le nom brut (ex. `Coloeus monedula`, alors que
l'univers et `species-data/base/` utilisent `Corvus monedula` : pas de photo, pas de
fiche, deux entrées pour la même espèce). Le contrat ne prévoit pas de rattrapage dans
`POST /admin/species-data/reload` ; ce module l'applique hors ligne (script
`server/scripts/recanonicalize.py`, serveur arrêté).

Effets, pour chaque `nom reçu → nom canonique` :
- `detections.scientific_name` ← canonique ; `detections.raw_scientific_name` est
  conservé tel quel (nom brut reçu, pour l'audit, contrat §9.1) ;
- `detections.redirected_to_scientific_name`, `predictions.scientific_name`,
  `kept_clips.scientific_name`, `species_site_rules.{scientific_name,
  redirect_to_scientific_name}`, `false_negative_reports.scientific_name` ← canonique
  (ces tables n'ont pas de colonne « nom brut ») ;
- cache `species_names` : la ligne de l'alias est fusionnée dans celle du canonique ;
- puis, pour chaque (site, espèce canonique) concernée : redirection recalculée depuis la
  règle du site, et top-5 clips recalculé (§4.3.1 : l'union des clips de l'alias et du
  canonique peut dépasser 5 ; les nouvelles entrées sans audio seront redemandées au
  prochain sync via `want_clips`).

Idempotent : relancé, il ne trouve plus rien à renommer et ne fait que recalculer
redirections et top-5 des espèces dont une détection porte un nom brut aliasé.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.ingest.redirect_recompute import recompute_redirect_for_site_species
from app.ingest.top5 import recompute_top5
from app.models.detection import Detection, Prediction
from app.models.false_negative import FalseNegativeReport
from app.models.kept_clip import KeptClip
from app.models.species_name import SpeciesName
from app.models.species_site_rule import SpeciesSiteRule


class AliasConflictError(RuntimeError):
    """Le rattrapage fusionnerait deux lignes qui ne peuvent pas coexister (ex. une règle
    sur l'alias ET une règle sur le canonique pour le même site) : rien n'est modifié,
    l'humain doit trancher."""


@dataclass
class RecanonicalizeReport:
    detections: int = 0
    redirect_targets: int = 0
    predictions: int = 0
    kept_clips: int = 0
    species_site_rules: int = 0
    false_negative_reports: int = 0
    species_names_merged: int = 0
    species_names_renamed: int = 0
    recomputed: list[tuple[int, str]] = field(default_factory=list)

    @property
    def renamed_rows(self) -> int:
        return (
            self.detections
            + self.redirect_targets
            + self.predictions
            + self.kept_clips
            + self.species_site_rules
            + self.false_negative_reports
            + self.species_names_merged
            + self.species_names_renamed
        )


def validate_aliases(aliases: dict[str, str]) -> None:
    """Contrat §7.3 : pas de chaîne (une valeur n'est jamais elle-même une clé), pas
    d'alias vers soi-même. Lève `ValueError` sinon."""
    for raw, canonical in aliases.items():
        if raw == canonical:
            raise ValueError(f"alias vers lui-même : {raw!r}")
        if canonical in aliases:
            raise ValueError(f"chaîne d'alias interdite : {raw!r} → {canonical!r} → {aliases[canonical]!r}")


def recanonicalize_existing(db: Session, aliases: dict[str, str]) -> RecanonicalizeReport:
    validate_aliases(aliases)
    _check_rule_conflicts(db, aliases)

    report = RecanonicalizeReport()
    for raw, canonical in aliases.items():
        report.detections += _rename(db, Detection.scientific_name, raw, canonical)
        report.redirect_targets += _rename(db, Detection.redirected_to_scientific_name, raw, canonical)
        report.predictions += _rename(db, Prediction.scientific_name, raw, canonical)
        report.kept_clips += _rename(db, KeptClip.scientific_name, raw, canonical)
        report.species_site_rules += _rename(db, SpeciesSiteRule.scientific_name, raw, canonical)
        report.species_site_rules += _rename(
            db, SpeciesSiteRule.redirect_to_scientific_name, raw, canonical
        )
        report.false_negative_reports += _rename(db, FalseNegativeReport.scientific_name, raw, canonical)
        _merge_species_name(db, raw, canonical, report)
    db.commit()

    # (site, canonique) dont au moins une détection a été reçue sous un alias : leur
    # redirection et leur top-5 doivent refléter la fusion.
    pairs = (
        db.query(Detection.site_id, Detection.scientific_name)
        .filter(Detection.raw_scientific_name.in_(list(aliases)))
        .distinct()
        .all()
    )
    for site_id, canonical in sorted(pairs):
        rule = (
            db.query(SpeciesSiteRule)
            .filter(
                SpeciesSiteRule.site_id == site_id,
                SpeciesSiteRule.scientific_name == canonical,
                SpeciesSiteRule.rule == "redirect",
            )
            .first()
        )
        recompute_redirect_for_site_species(
            db, site_id, canonical, rule.redirect_to_scientific_name if rule else None
        )
        db.commit()
        recompute_top5(db, site_id, canonical)
        report.recomputed.append((site_id, canonical))
    return report


def _rename(db: Session, column, raw: str, canonical: str) -> int:
    result = db.execute(
        update(column.class_).where(column == raw).values({column.key: canonical}),
        execution_options={"synchronize_session": False},
    )
    return result.rowcount or 0


def _merge_species_name(db: Session, raw: str, canonical: str, report: RecanonicalizeReport) -> None:
    alias_row = db.get(SpeciesName, raw)
    if alias_row is None:
        return
    canonical_row = db.get(SpeciesName, canonical)
    if canonical_row is None:
        db.add(
            SpeciesName(
                scientific_name=canonical,
                common_name_fr=alias_row.common_name_fr,
                source=alias_row.source,
                updated_at=alias_row.updated_at,
            )
        )
        report.species_names_renamed += 1
    else:
        if not canonical_row.common_name_fr and alias_row.common_name_fr:
            canonical_row.common_name_fr = alias_row.common_name_fr
        report.species_names_merged += 1
    db.delete(alias_row)
    db.flush()


def _check_rule_conflicts(db: Session, aliases: dict[str, str]) -> None:
    conflicts: list[str] = []
    for raw, canonical in aliases.items():
        alias_sites = {
            row.site_id
            for row in db.query(SpeciesSiteRule.site_id).filter(SpeciesSiteRule.scientific_name == raw)
        }
        if not alias_sites:
            continue
        both = (
            db.query(SpeciesSiteRule.site_id)
            .filter(SpeciesSiteRule.scientific_name == canonical, SpeciesSiteRule.site_id.in_(alias_sites))
            .all()
        )
        conflicts.extend(f"site {site_id} : règle sur {raw!r} et sur {canonical!r}" for (site_id,) in both)
    if conflicts:
        raise AliasConflictError("règles en conflit, à fusionner à la main : " + " ; ".join(conflicts))

"""Petits lookups partagés entre plusieurs routeurs navigateur."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models.site import Site
from app.models.species_site_rule import SpeciesSiteRule


def get_site_or_404(db: Session, slug: str) -> Site:
    site = db.query(Site).filter(Site.slug == slug).first()
    if site is None:
        raise ApiError(404, "site_not_found", f"Aucun site avec le slug « {slug} ».")
    return site


def impossible_names_for_site(db: Session, site_id: int) -> set[str]:
    return {
        row.scientific_name
        for row in db.query(SpeciesSiteRule.scientific_name).filter(
            SpeciesSiteRule.site_id == site_id, SpeciesSiteRule.rule == "impossible"
        )
    }


def rules_by_species_for_site(db: Session, site_id: int) -> dict[str, SpeciesSiteRule]:
    return {
        rule.scientific_name: rule
        for rule in db.query(SpeciesSiteRule).filter(SpeciesSiteRule.site_id == site_id)
    }

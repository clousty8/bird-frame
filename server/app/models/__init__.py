"""Importe tous les modèles pour que `Base.metadata` soit complet (Alembic, `create_all` des tests)."""

from app.models.base import Base
from app.models.detection import Detection, Prediction
from app.models.false_negative import FalseNegativeReport
from app.models.kept_clip import KeptClip
from app.models.node import Node, NodeStatus, NodeSyncState
from app.models.node_command import NodeCommand
from app.models.review import Review
from app.models.site import Site
from app.models.species_name import SpeciesName
from app.models.species_sheet import SpeciesSheet
from app.models.species_site_rule import SpeciesSiteRule

__all__ = [
    "Base",
    "Detection",
    "FalseNegativeReport",
    "KeptClip",
    "Node",
    "NodeCommand",
    "NodeStatus",
    "NodeSyncState",
    "Prediction",
    "Review",
    "Site",
    "SpeciesName",
    "SpeciesSheet",
    "SpeciesSiteRule",
]

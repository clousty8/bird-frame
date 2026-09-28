from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.time_utils import utc_now_str

# Contrat §5.2 : 11 valeurs. Seul `set_main_name` est créé par le périmètre serveur cœur
# (POST /nodes/register, WP-07) ; les autres appartiennent à des lots ultérieurs
# (WP-12/13/14/19) mais la colonne CHECK couvre déjà toute l'énumération pour que la
# migration n'ait pas à être retouchée quand ces lots arriveront.
COMMAND_KINDS = (
    "set_species_threshold",
    "exclude_species",
    "unexclude_species",
    "include_species",
    "uninclude_species",
    "reset_dynamic_threshold",
    "set_main_name",
    "mark_detection_reviewed",
    "start_live",
    "live_heartbeat",
    "stop_live",
)
COMMAND_STATUSES = ("pending", "delivered", "applied", "failed", "expired")


class NodeCommand(Base):
    """File de commandes serveur → nœud (architecture.md §4, étendu par le contrat §9.3)."""

    __tablename__ = "node_commands"
    __table_args__ = (
        CheckConstraint(
            "kind IN (" + ",".join(f"'{k}'" for k in COMMAND_KINDS) + ")",
            name="ck_node_command_kind",
        ),
        CheckConstraint(
            "status IN (" + ",".join(f"'{s}'" for s in COMMAND_STATUSES) + ")",
            name="ck_node_command_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_str)
    delivered_at: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_at: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[str | None] = mapped_column(String, nullable=True)
    result_json: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_type: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Clé opaque (uuid4) commune à toutes les commandes créées par un même appel
    # PUT/DELETE — ajout hors contrat (voir server/README.md « Décisions hors contrat »).
    # Sans elle, retrouver « les commandes du dernier PUT » d'une règle (contrat §6.20)
    # en comparant seulement `created_at` est fragile : deux écritures rapprochées (moins
    # d'une seconde d'écart, ex. script, ou double-clic) partagent la même seconde et
    # fusionneraient à tort deux lots de commandes.
    origin_batch: Mapped[str | None] = mapped_column(String, nullable=True)

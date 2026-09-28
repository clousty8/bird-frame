from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.time_utils import utc_now_str


class Node(Base):
    """Un nœud BirdNET-Go rattaché à un site (architecture.md §4).

    L'identité du site n'est jamais dérivée de `main.name` côté BirdNET-Go — assignée ici
    par le serveur à l'enregistrement (§7.1 du contrat).
    """

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tailscale_hostname: Mapped[str | None] = mapped_column(String, nullable=True)
    api_base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    bridge_shared_secret_hash: Mapped[str] = mapped_column(String, nullable=False)
    bearer_token_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_str)
    decommissioned_at: Mapped[str | None] = mapped_column(String, nullable=True)

    site: Mapped[Site] = relationship(back_populates="nodes")  # noqa: F821
    sync_state: Mapped[NodeSyncState] = relationship(
        back_populates="node", uselist=False, cascade="all, delete-orphan"
    )
    status: Mapped[NodeStatus] = relationship(
        back_populates="node", uselist=False, cascade="all, delete-orphan"
    )


class NodeSyncState(Base):
    """État canonique de synchro d'un nœud — porté par le SERVEUR (architecture.md §3.1)."""

    __tablename__ = "node_sync_state"

    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), primary_key=True)
    last_synced_detection_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sync_at: Mapped[str | None] = mapped_column(String, nullable=True)

    node: Mapped[Node] = relationship(back_populates="sync_state")


class NodeStatus(Base):
    """Supervision d'un nœud, alimentée par l'ingestion authentifiée et le heartbeat.

    Écarts par rapport au DDL brut d'architecture.md §4, imposés par le contrat §9.4 :
    `last_heartbeat_at`, `birdnet_go_reachable`, `node_db_max_id`,
    `dynamic_thresholds_snapshot_at` en plus. `birdnet_go_version` est ici (dynamique, mis
    à jour à chaque heartbeat) plutôt que sur `nodes` (qui serait statique et jamais
    revisité) — c'est la valeur que `NodeStatus.birdnet_go_version` expose au navigateur
    (§6.1 du contrat : « dernier heartbeat »).
    """

    __tablename__ = "node_status"

    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), primary_key=True)
    last_seen_at: Mapped[str | None] = mapped_column(String, nullable=True)
    last_heartbeat_at: Mapped[str | None] = mapped_column(String, nullable=True)
    last_detection_at: Mapped[str | None] = mapped_column(String, nullable=True)
    mic_device_name: Mapped[str | None] = mapped_column(String, nullable=True)
    mic_healthy: Mapped[bool | None] = mapped_column(nullable=True)
    disk_free_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    birdnet_go_pid_alive: Mapped[bool | None] = mapped_column(nullable=True)
    birdnet_go_reachable: Mapped[bool | None] = mapped_column(nullable=True)
    birdnet_go_version: Mapped[str | None] = mapped_column(String, nullable=True)
    bridge_version: Mapped[str | None] = mapped_column(String, nullable=True)
    node_db_max_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dynamic_thresholds_snapshot_json: Mapped[str | None] = mapped_column(String, nullable=True)
    dynamic_thresholds_snapshot_at: Mapped[str | None] = mapped_column(String, nullable=True)
    # Contrat §12.4 : `update_status` du dernier heartbeat (JSON `{state, target_version, error}`),
    # NULL si le bridge ne le rapporte pas.
    update_status_json: Mapped[str | None] = mapped_column(String, nullable=True)

    node: Mapped[Node] = relationship(back_populates="status")

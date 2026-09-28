from __future__ import annotations

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.time_utils import utc_now_str


class Site(Base):
    """Un lieu (architecture.md §4). `slug` est l'identifiant public, immuable."""

    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="Europe/Paris")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utc_now_str)

    nodes: Mapped[list[Node]] = relationship(back_populates="site")  # noqa: F821

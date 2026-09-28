"""Construction du moteur SQLAlchemy. Une instance par application (prod, ou une par
test) — voir `app/deps.py` pour la dépendance FastAPI qui expose la session courante.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings


def make_engine(app_settings: Settings) -> Engine:
    app_settings.db_path_resolved.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        app_settings.sqlalchemy_url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        # WAL : le serveur est lui-même écrit par plusieurs requêtes concurrentes
        # (ingestion, navigateur, tests) ; foreign_keys : on déclare des FK dans le
        # schéma, autant que SQLite les fasse réellement respecter.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False : le défaut de fileConfig() est True, ce qui coupe
    # silencieusement TOUS les loggers déjà configurés au moment de l'appel (dont ceux
    # d'uvicorn : "uvicorn", "uvicorn.error", "uvicorn.access"). Comme run_migrations()
    # (app/main.py) appelle `alembic upgrade head` programmatiquement au démarrage de
    # l'app (BIRDFRAME_AUTO_MIGRATE=1, valeur par défaut), sans ce paramètre plus AUCUN
    # log — y compris les logs d'accès et les erreurs applicatives — n'apparaît après la
    # migration, pour toute la durée de vie du process. Bug constaté et corrigé le
    # 27/09/2026 lors de l'intégration S1 (logs serveur muets après la ligne de migration).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _resolve_url() -> str:
    # `run_migrations()` (app/main.py) fixe explicitement sqlalchemy.url pour pointer sur
    # la base de l'app en cours (utile aux tests, une base temporaire par app). En usage
    # CLI (`uv run alembic upgrade head`), l'option est vide : on retombe sur la config
    # standard du serveur (BIRDFRAME_DB_PATH / .env).
    url = config.get_main_option("sqlalchemy.url") or get_settings().sqlalchemy_url
    # sqlite:///relative/or/absolute/path.db — le dossier parent doit exister avant que
    # sqlite3 n'essaie d'ouvrir le fichier, ce que ni Alembic ni sqlite3 ne font seuls.
    if url.startswith("sqlite:///"):
        from pathlib import Path

        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _resolve_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

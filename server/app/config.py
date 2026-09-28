"""Configuration du serveur, lue depuis les variables d'environnement BIRDFRAME_*.

Contrat §7.2 : tous les chemins relatifs sont résolus par rapport au dossier `server/`
(peu importe le `cwd` du process au démarrage), pour que `uvicorn app.main:app` lancé
depuis n'importe où fonctionne de façon prévisible.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# server/ (parent du package app/)
SERVER_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BIRDFRAME_",
        env_file=str(SERVER_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: str = "data/bird-frame.db"
    data_dir: str = "data"
    admin_token: str = ""
    host: str = "127.0.0.1"
    port: int = 8090
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    species_data_dir: str = "../species-data"
    sox_path: str = "sox"
    max_upload_mb: int = 25
    log_level: str = "info"
    auto_migrate: bool = True

    @property
    def db_path_resolved(self) -> Path:
        return _resolve(self.db_path)

    @property
    def data_dir_resolved(self) -> Path:
        return _resolve(self.data_dir)

    @property
    def species_data_dir_resolved(self) -> Path:
        return _resolve(self.species_data_dir)

    @property
    def clips_dir_resolved(self) -> Path:
        return self.data_dir_resolved / "clips"

    @property
    def photos_dir_resolved(self) -> Path:
        return self.data_dir_resolved / "photos"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        return f"sqlite:///{self.db_path_resolved}"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (SERVER_DIR / p).resolve()


def get_settings() -> Settings:
    """Recharge la config à chaque appel (utile pour les tests qui changent l'environnement)."""
    return Settings()


# Instance par défaut utilisée par le code applicatif (pas les tests, qui appellent
# get_settings() ou injectent la leur).
settings = get_settings()

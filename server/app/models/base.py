from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base déclarative SQLAlchemy 2.x partagée par tous les modèles du serveur."""

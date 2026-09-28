"""node_status: update_status_json (état de la mise à jour automatique du bridge, contrat §12)

Revision ID: 7c4e2a9d1f36
Revises: eed8a20222f8
Create Date: 2026-09-28 10:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c4e2a9d1f36'
down_revision: Union[str, None] = 'eed8a20222f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('node_status', sa.Column('update_status_json', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('node_status', 'update_status_json')

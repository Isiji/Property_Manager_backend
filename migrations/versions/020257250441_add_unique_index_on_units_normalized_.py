"""add unique index on units normalized label

Revision ID: 020257250441
Revises: add_units_unique_idx
Create Date: 2025-11-04 16:20:09.745280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '020257250441'
down_revision: Union[str, Sequence[str], None] = 'add_units_unique_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

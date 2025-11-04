"""merge heads 020257250441 + a1b2c3

Revision ID: merge_20251104_01
Revises: 020257250441, a1b2c3
Create Date: 2025-11-04
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_20251104_01'
down_revision = ('020257250441', 'a1b2c3')
branch_labels = None
depends_on = None


def upgrade():
    # No schema change; this only merges branches.
    pass


def downgrade():
    # Usually no need to "unmerge".
    pass

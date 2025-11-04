"""add unique index on (property_id, lower(trim(number))) for units

Revision ID: add_units_unique_idx
Revises: <PUT_PREVIOUS_REVISION_ID_HERE>
Create Date: 2025-11-04

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_units_unique_idx'
down_revision = 'c0a4079be575'
branch_labels = None
depends_on = None


def upgrade():
    # Optional: backfill normalization by trimming whitespace
    op.execute("""
        UPDATE units
        SET number = TRIM(number)
        WHERE number IS NOT NULL
    """)

    # Create a unique index on normalized label (lower + trim)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_units_property_norm_number
        ON units (property_id, lower(trim(number)));
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_units_property_norm_number;")

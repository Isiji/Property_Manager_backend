"""add payments.reference

Revision ID: ref_pay_251106
Revises: merge_20251104_01
Create Date: 2025-11-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "ref_pay_251106"
down_revision = "merge_20251104_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payments",
        sa.Column("reference", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_payments_reference_not_null",
        "payments",
        ["reference"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_payments_reference_not_null", table_name="payments")
    op.drop_column("payments", "reference")

"""add payment fields and payment allocations

Revision ID: add_payment_fields_and_allocations
Revises: 1c663cedf39c
Create Date: 2026-03-24 14:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "add_payment_fields_and_allocations"
down_revision: Union[str, Sequence[str], None] = "1c663cedf39c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("payment_method", sa.String(length=40), nullable=True))
    op.add_column("payments", sa.Column("allocation_mode", sa.String(length=30), nullable=True))
    op.add_column("payments", sa.Column("selected_periods_json", sa.String(), nullable=True))
    op.add_column("payments", sa.Column("notes", sa.String(), nullable=True))

    # drop old unique per month rule if it exists
    try:
        op.drop_constraint("uq_payments_lease_period", "payments", type_="unique")
    except Exception:
        pass

    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("lease_id", sa.Integer(), nullable=True),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("amount_applied", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.ForeignKeyConstraint(["lease_id"], ["leases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_payment_allocations_payment_period",
        "payment_allocations",
        ["payment_id", "period"],
        unique=False,
    )
    op.create_index(
        "ix_payment_allocations_lease_period",
        "payment_allocations",
        ["lease_id", "period"],
        unique=False,
    )
    op.create_index(
        "ix_payment_allocations_tenant_period",
        "payment_allocations",
        ["tenant_id", "period"],
        unique=False,
    )

    op.add_column("payment_receipts", sa.Column("allocations_json", sa.String(), nullable=True))
    op.alter_column("payment_receipts", "period", existing_type=sa.String(length=7), nullable=True)


def downgrade() -> None:
    op.alter_column("payment_receipts", "period", existing_type=sa.String(length=7), nullable=False)
    op.drop_column("payment_receipts", "allocations_json")

    op.drop_index("ix_payment_allocations_tenant_period", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_lease_period", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_payment_period", table_name="payment_allocations")
    op.drop_table("payment_allocations")

    op.add_unique_constraint("uq_payments_lease_period", "payments", ["lease_id", "period"])

    op.drop_column("payments", "notes")
    op.drop_column("payments", "selected_periods_json")
    op.drop_column("payments", "allocation_mode")
    op.drop_column("payments", "payment_method")
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_mpesa_request_ids_to_payments"
down_revision = "20260129_fix_agency_assignment_unique"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payments",
        sa.Column("merchant_request_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("checkout_request_id", sa.String(length=100), nullable=True),
    )

    op.create_index(
        "ix_payments_merchant_request_id",
        "payments",
        ["merchant_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_payments_checkout_request_id",
        "payments",
        ["checkout_request_id"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_payments_checkout_request_id", table_name="payments")
    op.drop_index("ix_payments_merchant_request_id", table_name="payments")

    op.drop_column("payments", "checkout_request_id")
    op.drop_column("payments", "merchant_request_id")
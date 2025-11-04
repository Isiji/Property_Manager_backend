"""initial tables (second idempotent patch)

Revision ID: 9062b63176a0
Revises: 9dd8cb16e1e1
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9062b63176a0'
down_revision = '9dd8cb16e1e1'
branch_labels = None
depends_on = None


def upgrade():
    # Make this revision safe to re-run after prior patches.
    # 1) Add payments.lease_id only if missing
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'payments'
        ) THEN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'payments' AND column_name = 'lease_id'
            ) THEN
                ALTER TABLE payments ADD COLUMN lease_id INTEGER;
            END IF;
        END IF;
    END $$;
    """)

    # 2) Add FK only if missing
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'payments'
        ) THEN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'payments'::regclass
                  AND conname = 'fk_payments_lease_id_leases'
            ) THEN
                ALTER TABLE payments
                ADD CONSTRAINT fk_payments_lease_id_leases
                FOREIGN KEY (lease_id) REFERENCES leases(id)
                ON DELETE SET NULL;
            END IF;
        END IF;
    END $$;
    """)

    # 3) (No-op hardening) Ensure index on payments.lease_id exists, optional
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'payments' AND column_name = 'lease_id'
        ) THEN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'payments'
                  AND indexname = 'ix_payments_lease_id'
            ) THEN
                CREATE INDEX ix_payments_lease_id ON payments(lease_id);
            END IF;
        END IF;
    END $$;
    """)


def downgrade():
    # Be conservative: drop the FK if present; keep the column to avoid data loss.
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'payments'::regclass
              AND conname = 'fk_payments_lease_id_leases'
        ) THEN
            ALTER TABLE payments DROP CONSTRAINT fk_payments_lease_id_leases;
        END IF;
    END $$;
    """)

    # Drop index if it exists (optional symmetry)
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'payments'
              AND indexname = 'ix_payments_lease_id'
        ) THEN
            DROP INDEX ix_payments_lease_id;
        END IF;
    END $$;
    """)

"""initial tables (idempotent patch)

Revision ID: 9dd8cb16e1e1
Revises: 74668739e4cb
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9dd8cb16e1e1'
down_revision = '74668739e4cb'
branch_labels = None
depends_on = None


def upgrade():
    # --- Ensure payments table exists before altering (safe no-op if it does not) ---
    # If your project always creates `payments` earlier, this block is harmless.
    # Keeping it light: we won't CREATE TABLE here—only alter checks.

    # 1) Add payments.lease_id if missing
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

    # 2) Add FK payments(lease_id) -> leases(id) if missing
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

    # 3) (Optional hardening) Make sure paid_date exists as DATE if your chain expects it
    #    This will only add the column when missing; won’t touch existing data/type.
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'payments'
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payments' AND column_name = 'paid_date'
            ) THEN
                ALTER TABLE payments ADD COLUMN paid_date DATE;
            END IF;
        END IF;
    END $$;
    """)

    # 4) (Optional) Ensure period column exists, commonly used in your reports
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'payments'
        ) THEN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'payments' AND column_name = 'period'
            ) THEN
                ALTER TABLE payments ADD COLUMN period VARCHAR;
            END IF;
        END IF;
    END $$;
    """)


def downgrade():
    # Be conservative to avoid data loss: drop only the FK if it exists.
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
    # Intentionally keep columns in downgrade to avoid breaking older data.

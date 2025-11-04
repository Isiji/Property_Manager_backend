"""fix payment relationships & normalize paid_date

Revision ID: 1b14747a5306
Revises: 986bc3e7265a
Create Date: 2025-XX-XX
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1b14747a5306'
down_revision = '986bc3e7265a'
branch_labels = None
depends_on = None


def upgrade():
    # --- 1) If legacy "date" column exists, rename it to "paid_date"
    # Use a DO block to avoid errors on installations that never had "date"
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'payments'
              AND column_name = 'date'
        ) THEN
            ALTER TABLE payments RENAME COLUMN "date" TO paid_date;
        END IF;
    END $$;
    """)

    # --- 2) Ensure "paid_date" exists (for installs that had neither date nor paid_date yet)
    # Add it if missing; make it nullable
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'payments'
              AND column_name = 'paid_date'
        ) THEN
            ALTER TABLE payments
            ADD COLUMN paid_date DATE NULL;
        END IF;
    END $$;
    """)

    # --- 3) Make sure paid_date is nullable (some older migrations set NOT NULL)
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'payments'
              AND column_name = 'paid_date'
        ) THEN
            ALTER TABLE payments ALTER COLUMN paid_date DROP NOT NULL;
        END IF;
    END $$;
    """)

    # --- 4) Optional: ensure period is TEXT/VARCHAR and present (skip if you already have it)
    # Comment out if your prior migration already created it correctly.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'payments'
              AND column_name = 'period'
        ) THEN
            ALTER TABLE payments ADD COLUMN period VARCHAR(16);
        END IF;
    END $$;
    """)

    # --- 5) Ensure tenant/lease FKs match your current models (idempotent-ish)
    # Create columns if missing, then add FKs if missing.
    op.execute("""
    DO $$
    BEGIN
        -- tenant_id
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'payments' AND column_name = 'tenant_id'
        ) THEN
            ALTER TABLE payments ADD COLUMN tenant_id INTEGER;
        END IF;

        -- lease_id
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'payments' AND column_name = 'lease_id'
        ) THEN
            ALTER TABLE payments ADD COLUMN lease_id INTEGER;
        END IF;
    END $$;
    """)

    # Add foreign keys if they don't exist yet
    # (We can try to create them; if they exist, ignore errors using IF NOT EXISTS patterns via DO block.)
    op.execute("""
    DO $$
    BEGIN
        -- tenant_id FK
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'payments'::regclass
              AND conname = 'fk_payments_tenant_id_tenants'
        ) THEN
            ALTER TABLE payments
            ADD CONSTRAINT fk_payments_tenant_id_tenants
            FOREIGN KEY (tenant_id) REFERENCES tenants (id)
            ON DELETE SET NULL;
        END IF;

        -- lease_id FK
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'payments'::regclass
              AND conname = 'fk_payments_lease_id_leases'
        ) THEN
            ALTER TABLE payments
            ADD CONSTRAINT fk_payments_lease_id_leases
            FOREIGN KEY (lease_id) REFERENCES leases (id)
            ON DELETE SET NULL;
        END IF;
    END $$;
    """)


def downgrade():
    # We’ll be conservative on downgrade: drop FKs we added and leave columns (safer for data)
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'payments'::regclass
              AND conname = 'fk_payments_tenant_id_tenants'
        ) THEN
            ALTER TABLE payments DROP CONSTRAINT fk_payments_tenant_id_tenants;
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'payments'::regclass
              AND conname = 'fk_payments_lease_id_leases'
        ) THEN
            ALTER TABLE payments DROP CONSTRAINT fk_payments_lease_id_leases;
        END IF;
    END $$;
    """)
    # Leave paid_date/period columns in place to avoid data loss on downgrade.

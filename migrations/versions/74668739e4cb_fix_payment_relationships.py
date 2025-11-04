"""fix payment relationships (idempotent)

Revision ID: 74668739e4cb
Revises: 387aad083c44
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '74668739e4cb'
down_revision = '387aad083c44'
branch_labels = None
depends_on = None


def upgrade():
    # leases.rent_amount — add if missing; otherwise ensure type/nullability
    op.execute("""
    DO $$
    BEGIN
        -- Add the column if it does not exist
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'leases' AND column_name = 'rent_amount'
        ) THEN
            ALTER TABLE leases
            ADD COLUMN rent_amount NUMERIC(10,2) NOT NULL DEFAULT 0;
            -- Drop default so future inserts must provide a value
            ALTER TABLE leases ALTER COLUMN rent_amount DROP DEFAULT;
        ELSE
            -- Ensure the type is NUMERIC(10,2) if possible
            BEGIN
                ALTER TABLE leases ALTER COLUMN rent_amount TYPE NUMERIC(10,2);
            EXCEPTION WHEN others THEN
                -- Ignore if already a compatible numeric type
                NULL;
            END;

            -- Try to enforce NOT NULL; if data has NULLs, keep it nullable
            BEGIN
                ALTER TABLE leases ALTER COLUMN rent_amount SET NOT NULL;
            EXCEPTION WHEN others THEN
                NULL;
            END;
        END IF;
    END $$;
    """)

    # Ensure leases.start_date exists (DATE)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'leases' AND column_name = 'start_date'
        ) THEN
            ALTER TABLE leases ADD COLUMN start_date DATE;
        END IF;
    END $$;
    """)

    # Ensure leases.end_date exists (DATE)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'leases' AND column_name = 'end_date'
        ) THEN
            ALTER TABLE leases ADD COLUMN end_date DATE;
        END IF;
    END $$;
    """)

    # Ensure leases.active exists (INTEGER or BOOLEAN; keeping INTEGER here to match earlier assumptions)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'leases' AND column_name = 'active'
        ) THEN
            ALTER TABLE leases ADD COLUMN active INTEGER DEFAULT 1;
            ALTER TABLE leases ALTER COLUMN active DROP DEFAULT;
        END IF;
    END $$;
    """)

    # Idempotent foreign keys for tenant_id and unit_id
    op.execute("""
    DO $$
    BEGIN
        -- tenant_id column and FK
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'leases' AND column_name = 'tenant_id'
        ) THEN
            ALTER TABLE leases ADD COLUMN tenant_id INTEGER;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'leases'::regclass
              AND conname = 'fk_leases_tenant_id_tenants'
        ) THEN
            ALTER TABLE leases
            ADD CONSTRAINT fk_leases_tenant_id_tenants
            FOREIGN KEY (tenant_id) REFERENCES tenants (id)
            ON DELETE SET NULL;
        END IF;

        -- unit_id column and FK
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'leases' AND column_name = 'unit_id'
        ) THEN
            ALTER TABLE leases ADD COLUMN unit_id INTEGER;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'leases'::regclass
              AND conname = 'fk_leases_unit_id_units'
        ) THEN
            ALTER TABLE leases
            ADD CONSTRAINT fk_leases_unit_id_units
            FOREIGN KEY (unit_id) REFERENCES units (id)
            ON DELETE SET NULL;
        END IF;
    END $$;
    """)


def downgrade():
    # Be conservative: drop only the FKs we added if present.
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'leases'::regclass
              AND conname = 'fk_leases_tenant_id_tenants'
        ) THEN
            ALTER TABLE leases DROP CONSTRAINT fk_leases_tenant_id_tenants;
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'leases'::regclass
              AND conname = 'fk_leases_unit_id_units'
        ) THEN
            ALTER TABLE leases DROP CONSTRAINT fk_leases_unit_id_units;
        END IF;
    END $$;
    """)
    # Intentionally keep columns in downgrade to avoid data loss.

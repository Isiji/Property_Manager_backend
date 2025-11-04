"""add id_number to user tables (idempotent)

Revision ID: a1b2c3
Revises: e028c291e455
Create Date: 2025-01-02
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3"
down_revision = "e028c291e455"
branch_labels = None
depends_on = None


def upgrade():
    # Add id_number to all user-like tables if missing (nullable=True)
    op.execute(
        """
        DO $$
        DECLARE
            t TEXT;
            tbls TEXT[] := ARRAY['tenants','landlords','property_managers','admins'];
        BEGIN
            FOREACH t IN ARRAY tbls LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema='public' AND table_name=t
                ) THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=t AND column_name='id_number'
                    ) THEN
                        EXECUTE format('ALTER TABLE %I ADD COLUMN id_number VARCHAR', t);
                    END IF;
                END IF;
            END LOOP;
        END $$;
        """
    )
    # If later you want an index, we can add guarded CREATE INDEX; for now we keep it simple and safe.


def downgrade():
    # Drop id_number if it exists (be conservative)
    op.execute(
        """
        DO $$
        DECLARE
            t TEXT;
            tbls TEXT[] := ARRAY['tenants','landlords','property_managers','admins'];
        BEGIN
            FOREACH t IN ARRAY tbls LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=t AND column_name='id_number'
                ) THEN
                    EXECUTE format('ALTER TABLE %I DROP COLUMN id_number', t);
                END IF;
            END LOOP;
        END $$;
        """
    )

"""add password column to landlords (idempotent)

Revision ID: e028c291e455
Revises: 9062b63176a0
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e028c291e455"
down_revision = "9062b63176a0"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Add landlords.password only if it doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'landlords'
            ) THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'landlords'
                      AND column_name = 'password'
                ) THEN
                    -- Add as nullable first to avoid default/backfill issues
                    ALTER TABLE landlords ADD COLUMN password VARCHAR;
                END IF;
            END IF;
        END $$;
        """
    )

    # 2) If the column exists and there are NO NULLs, enforce NOT NULL.
    #    If there are any NULLs, we leave it nullable so we don't break existing data.
    op.execute(
        """
        DO $$
        DECLARE
            col_exists BOOLEAN;
            null_count BIGINT;
        BEGIN
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'landlords'
                  AND column_name = 'password'
            ) INTO col_exists;

            IF col_exists THEN
                EXECUTE 'SELECT COUNT(*) FROM landlords WHERE password IS NULL' INTO null_count;

                IF null_count = 0 THEN
                    -- Safe to enforce NOT NULL
                    ALTER TABLE landlords ALTER COLUMN password SET NOT NULL;
                END IF;
            END IF;
        END $$;
        """
    )


def downgrade():
    # Be conservative: only drop the column if it exists.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'landlords'
                  AND column_name = 'password'
            ) THEN
                ALTER TABLE landlords DROP COLUMN password;
            END IF;
        END $$;
        """
    )

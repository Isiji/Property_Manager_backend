from alembic import op
import sqlalchemy as sa

revision = "add_reference_to_payments_20251106"
down_revision = "merge_20251104_01"

def upgrade() -> None:
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS reference VARCHAR(64)")

def downgrade() -> None:
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS reference")

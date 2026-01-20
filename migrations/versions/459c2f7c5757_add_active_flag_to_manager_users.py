from alembic import op
import sqlalchemy as sa

revision = "459c2f7c5757"
down_revision = "335ddea87776"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "manager_users",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true"))
    )

    # Backfill: if you previously used staff_role='inactive', mark those inactive
    op.execute("""
        UPDATE manager_users
        SET active = false
        WHERE lower(coalesce(staff_role, '')) = 'inactive'
    """)

    # Optional: drop server default after adding (cleaner), safe to keep too
    op.alter_column("manager_users", "active", server_default=None)

def downgrade():
    op.drop_column("manager_users", "active")

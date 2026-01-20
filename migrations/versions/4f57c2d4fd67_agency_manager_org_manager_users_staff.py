from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "4f57c2d4fd67"
down_revision = "c11a6d858826"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_tables = set(inspector.get_table_names())
    pm_cols = {c["name"] for c in inspector.get_columns("property_managers")}

    # 1) Add org fields to property_managers (only if missing)
    if "type" not in pm_cols:
        op.add_column("property_managers", sa.Column("type", sa.String(), nullable=False, server_default="individual"))
    if "company_name" not in pm_cols:
        op.add_column("property_managers", sa.Column("company_name", sa.String(), nullable=True))
    if "contact_person" not in pm_cols:
        op.add_column("property_managers", sa.Column("contact_person", sa.String(), nullable=True))
    if "office_phone" not in pm_cols:
        op.add_column("property_managers", sa.Column("office_phone", sa.String(), nullable=True))
    if "office_email" not in pm_cols:
        op.add_column("property_managers", sa.Column("office_email", sa.String(), nullable=True))
    if "logo_url" not in pm_cols:
        op.add_column("property_managers", sa.Column("logo_url", sa.String(), nullable=True))

    # 2) Make property_managers.password nullable (safe to re-run)
    op.alter_column("property_managers", "password", existing_type=sa.String(), nullable=True)

    # 3) Ensure manager_users table exists, and has required columns/indexes
    if "manager_users" not in existing_tables:
        # Create table with the full expected schema
        op.create_table(
            "manager_users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("manager_id", sa.Integer(), sa.ForeignKey("property_managers.id"), nullable=False, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("phone", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("id_number", sa.String(), nullable=True),
            sa.Column("staff_role", sa.String(), nullable=False, server_default="manager_staff"),
        )
        op.create_index("ix_manager_users_phone", "manager_users", ["phone"], unique=True)
        op.create_index("ix_manager_users_email", "manager_users", ["email"], unique=True)

    else:
        # Table exists: patch missing columns
        mu_cols = {c["name"] for c in inspector.get_columns("manager_users")}
        if "id_number" not in mu_cols:
            op.add_column("manager_users", sa.Column("id_number", sa.String(), nullable=True))
        if "staff_role" not in mu_cols:
            op.add_column(
                "manager_users",
                sa.Column("staff_role", sa.String(), nullable=False, server_default="manager_staff"),
            )

        # Patch missing password_hash column if it doesn't exist (rare but safe)
        if "password_hash" not in mu_cols:
            op.add_column("manager_users", sa.Column("password_hash", sa.String(), nullable=True))

        # Ensure indexes exist (create if missing)
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("manager_users")}
        if "ix_manager_users_phone" not in existing_indexes:
            op.create_index("ix_manager_users_phone", "manager_users", ["phone"], unique=True)
        if "ix_manager_users_email" not in existing_indexes:
            op.create_index("ix_manager_users_email", "manager_users", ["email"], unique=True)

    # 4) Backfill:
    # Insert staff accounts for PropertyManagers with passwords,
    # but only if manager_users doesn't already have that phone.
    # NOTE: staff_role column exists now, so this won't fail.
    op.execute("""
        INSERT INTO manager_users (manager_id, name, phone, email, password_hash, id_number, staff_role)
        SELECT pm.id, pm.name, pm.phone, pm.email, pm.password, pm.id_number, 'manager_admin'
        FROM property_managers pm
        WHERE pm.password IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM manager_users mu WHERE mu.phone = pm.phone
          );
    """)

    # 5) If password_hash was nullable (because we patched), enforce non-null where possible
    # (leave existing nulls if your old table had them; your app will handle only proper accounts)
    # Optional: you can later manually clean up rows with null password_hash.
    op.execute("""
        UPDATE manager_users
        SET password_hash = password_hash
        WHERE password_hash IS NOT NULL;
    """)

    # 6) Null out old org passwords so manager login is staff-based
    op.execute("UPDATE property_managers SET password = NULL;")


def downgrade():
    # Conservative downgrade: do nothing (prevents accidental data loss if table pre-existed)
    pass

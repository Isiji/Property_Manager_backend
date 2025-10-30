"""add id_number to user tables"""

from alembic import op
import sqlalchemy as sa

# Short, tidy identifiers
revision = "a1b2c3"
down_revision = "e028c291e455"
branch_labels = None
depends_on = None

def upgrade():
    # Tenants
    op.add_column("tenants", sa.Column("id_number", sa.String(), nullable=True))
    op.create_index("ix_tenants_id_number", "tenants", ["id_number"], unique=False)

    # Landlords
    op.add_column("landlords", sa.Column("id_number", sa.String(), nullable=True))
    op.create_index("ix_landlords_id_number", "landlords", ["id_number"], unique=False)

    # Property Managers
    op.add_column("property_managers", sa.Column("id_number", sa.String(), nullable=True))
    op.create_index("ix_property_managers_id_number", "property_managers", ["id_number"], unique=False)

    # Admins
    op.add_column("admins", sa.Column("id_number", sa.String(), nullable=True))
    op.create_index("ix_admins_id_number", "admins", ["id_number"], unique=False)


def downgrade():
    # Admins
    op.drop_index("ix_admins_id_number", table_name="admins")
    op.drop_column("admins", "id_number")

    # Property Managers
    op.drop_index("ix_property_managers_id_number", table_name="property_managers")
    op.drop_column("property_managers", "id_number")

    # Landlords
    op.drop_index("ix_landlords_id_number", table_name="landlords")
    op.drop_column("landlords", "id_number")

    # Tenants
    op.drop_index("ix_tenants_id_number", table_name="tenants")
    op.drop_column("tenants", "id_number")

"""Fix agency assignment unique constraints

Revision ID: 20260129_fix_agency_assignment_unique
Revises: 733fde1d33ee
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260129_fix_agency_assignment_unique"
down_revision = "733fde1d33ee"
branch_labels = None
depends_on = None


def upgrade():
    # -----------------------------
    # STAFF assignments: drop bad constraint if exists
    # -----------------------------
    # Old constraint name from your error:
    # uq_property_assignment_active
    op.drop_constraint(
        "uq_property_assignment_active",
        "property_agent_assignments",
        type_="unique",
    )

    # Create partial unique index: one active per property
    op.create_index(
        "ux_property_agent_assignment_one_active_per_property",
        "property_agent_assignments",
        ["property_id"],
        unique=True,
        postgresql_where=sa.text("active IS TRUE"),
    )

    # -----------------------------
    # EXTERNAL assignments: drop old unique constraint if you had it
    # (you currently had uq_property_external_assignment_active)
    # -----------------------------
    op.drop_constraint(
        "uq_property_external_assignment_active",
        "property_external_manager_assignments",
        type_="unique",
    )

    # Create partial unique index: one active per property
    op.create_index(
        "ux_property_external_assignment_one_active_per_property",
        "property_external_manager_assignments",
        ["property_id"],
        unique=True,
        postgresql_where=sa.text("active IS TRUE"),
    )


def downgrade():
    # Drop new indexes
    op.drop_index("ux_property_external_assignment_one_active_per_property", table_name="property_external_manager_assignments")
    op.drop_index("ux_property_agent_assignment_one_active_per_property", table_name="property_agent_assignments")

    # Recreate old constraints (not recommended, but for downgrade completeness)
    op.create_unique_constraint(
        "uq_property_external_assignment_active",
        "property_external_manager_assignments",
        ["property_id", "active"],
    )

    op.create_unique_constraint(
        "uq_property_assignment_active",
        "property_agent_assignments",
        ["property_id", "assignee_user_id", "active"],
    )

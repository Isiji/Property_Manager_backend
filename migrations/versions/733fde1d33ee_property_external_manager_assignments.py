from alembic import op
import sqlalchemy as sa

revision = "733fde1d33ee"
down_revision = "459c2f7c5757"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "property_external_manager_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("agent_manager_id", sa.Integer(), sa.ForeignKey("property_managers.id"), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), sa.ForeignKey("manager_users.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("property_id", "active", name="uq_property_external_assignment_active"),
    )

    op.create_index(
        "ix_property_external_manager_assignments_property_id",
        "property_external_manager_assignments",
        ["property_id"],
    )
    op.create_index(
        "ix_property_external_manager_assignments_agent_manager_id",
        "property_external_manager_assignments",
        ["agent_manager_id"],
    )
    op.create_index(
        "ix_property_external_manager_assignments_assigned_by_user_id",
        "property_external_manager_assignments",
        ["assigned_by_user_id"],
    )

    op.alter_column("property_external_manager_assignments", "active", server_default=None)

def downgrade():
    op.drop_index("ix_property_external_manager_assignments_assigned_by_user_id", table_name="property_external_manager_assignments")
    op.drop_index("ix_property_external_manager_assignments_agent_manager_id", table_name="property_external_manager_assignments")
    op.drop_index("ix_property_external_manager_assignments_property_id", table_name="property_external_manager_assignments")
    op.drop_table("property_external_manager_assignments")

from alembic import op
import sqlalchemy as sa


revision = "335ddea87776"
down_revision = "4f57c2d4fd67"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agency_agent_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agency_manager_id", sa.Integer(), sa.ForeignKey("property_managers.id"), nullable=False),
        sa.Column("agent_manager_id", sa.Integer(), sa.ForeignKey("property_managers.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("agency_manager_id", "agent_manager_id", name="uq_agency_agent_link"),
    )
    op.create_index("ix_agency_agent_links_agency_manager_id", "agency_agent_links", ["agency_manager_id"])
    op.create_index("ix_agency_agent_links_agent_manager_id", "agency_agent_links", ["agent_manager_id"])

    op.create_table(
        "property_agent_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("assignee_user_id", sa.Integer(), sa.ForeignKey("manager_users.id"), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), sa.ForeignKey("manager_users.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("property_id", "assignee_user_id", "active", name="uq_property_assignment_active"),
    )
    op.create_index("ix_property_agent_assignments_property_id", "property_agent_assignments", ["property_id"])
    op.create_index("ix_property_agent_assignments_assignee_user_id", "property_agent_assignments", ["assignee_user_id"])
    op.create_index("ix_property_agent_assignments_assigned_by_user_id", "property_agent_assignments", ["assigned_by_user_id"])


def downgrade():
    op.drop_index("ix_property_agent_assignments_assigned_by_user_id", table_name="property_agent_assignments")
    op.drop_index("ix_property_agent_assignments_assignee_user_id", table_name="property_agent_assignments")
    op.drop_index("ix_property_agent_assignments_property_id", table_name="property_agent_assignments")
    op.drop_table("property_agent_assignments")

    op.drop_index("ix_agency_agent_links_agent_manager_id", table_name="agency_agent_links")
    op.drop_index("ix_agency_agent_links_agency_manager_id", table_name="agency_agent_links")
    op.drop_table("agency_agent_links")

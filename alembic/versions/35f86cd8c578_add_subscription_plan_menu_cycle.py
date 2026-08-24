"""add subscription plan menu cycle

Revision ID: 35f86cd8c578
Revises: 4e2a64a85163
Create Date: 2026-08-24 13:18:13.676034
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# =========================================================
# REVISION IDENTIFIERS
# =========================================================

revision: str = "35f86cd8c578"

down_revision: Union[str, Sequence[str], None] = "4e2a64a85163"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# =========================================================
# UPGRADE
# =========================================================

def upgrade() -> None:

    op.create_table(
        "subscription_plan_menu_cycle",

        # -------------------------------------------------
        # PRIMARY KEY
        # -------------------------------------------------

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        # -------------------------------------------------
        # SUBSCRIPTION PLAN
        # -------------------------------------------------

        sa.Column(
            "plan_id",
            sa.String(),
            nullable=False,
        ),

        # -------------------------------------------------
        # CYCLE DAY
        # 1 → 30
        # -------------------------------------------------

        sa.Column(
            "day_number",
            sa.Integer(),
            nullable=False,
        ),

        # -------------------------------------------------
        # MEAL TYPE
        # breakfast / lunch / dinner
        # -------------------------------------------------

        sa.Column(
            "meal_type",
            sa.String(),
            nullable=False,
        ),

        # -------------------------------------------------
        # EXISTING MENU
        # -------------------------------------------------

        sa.Column(
            "menu_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        # -------------------------------------------------
        # TIMESTAMPS
        # -------------------------------------------------

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # -------------------------------------------------
        # FOREIGN KEYS
        # -------------------------------------------------

        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["subscription_plans.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["menu_id"],
            ["menus.id"],
            ondelete="RESTRICT",
        ),

        # -------------------------------------------------
        # PRIMARY KEY
        # -------------------------------------------------

        sa.PrimaryKeyConstraint("id"),

        # -------------------------------------------------
        # ONE MEAL TYPE PER DAY PER PLAN
        # -------------------------------------------------

        sa.UniqueConstraint(
            "plan_id",
            "day_number",
            "meal_type",
            name="uq_subscription_plan_cycle_day_meal",
        ),
    )

    # =====================================================
    # INDEXES
    # =====================================================

    op.create_index(
        "idx_subscription_plan_cycle_plan_day",
        "subscription_plan_menu_cycle",
        ["plan_id", "day_number"],
        unique=False,
    )

    op.create_index(
        "idx_subscription_plan_cycle_menu",
        "subscription_plan_menu_cycle",
        ["menu_id"],
        unique=False,
    )

    op.create_index(
        "ix_subscription_plan_menu_cycle_plan_id",
        "subscription_plan_menu_cycle",
        ["plan_id"],
        unique=False,
    )

    op.create_index(
        "ix_subscription_plan_menu_cycle_menu_id",
        "subscription_plan_menu_cycle",
        ["menu_id"],
        unique=False,
    )


# =========================================================
# DOWNGRADE
# =========================================================

def downgrade() -> None:

    # -----------------------------------------------------
    # DROP INDEXES
    # -----------------------------------------------------

    op.drop_index(
        "ix_subscription_plan_menu_cycle_menu_id",
        table_name="subscription_plan_menu_cycle",
    )

    op.drop_index(
        "ix_subscription_plan_menu_cycle_plan_id",
        table_name="subscription_plan_menu_cycle",
    )

    op.drop_index(
        "idx_subscription_plan_cycle_menu",
        table_name="subscription_plan_menu_cycle",
    )

    op.drop_index(
        "idx_subscription_plan_cycle_plan_day",
        table_name="subscription_plan_menu_cycle",
    )

    # -----------------------------------------------------
    # DROP TABLE
    # -----------------------------------------------------

    op.drop_table(
        "subscription_plan_menu_cycle"
    )
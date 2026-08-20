"""add menu cycle and date overrides

Revision ID: 90e453b9b2ab
Revises: e3b06754b73e
Create Date: 2026-08-19 12:39:29.106372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "90e453b9b2ab"
down_revision: Union[str, Sequence[str], None] = "e3b06754b73e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # =========================================================
    # MENU CYCLE
    # =========================================================

    op.create_table(
        "menu_cycles",

        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "chef_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "menu_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "cycle_day",
            sa.Integer(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["chef_id"],
            ["users.id"],
        ),

        sa.ForeignKeyConstraint(
            ["menu_id"],
            ["menus.id"],
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "chef_id",
            "cycle_day",
            name="uq_menu_cycle_chef_day",
        ),
    )

    op.create_index(
        "idx_menu_cycle_chef_day",
        "menu_cycles",
        ["chef_id", "cycle_day"],
        unique=False,
    )

    op.create_index(
        "ix_menu_cycles_chef_id",
        "menu_cycles",
        ["chef_id"],
        unique=False,
    )

    op.create_index(
        "ix_menu_cycles_menu_id",
        "menu_cycles",
        ["menu_id"],
        unique=False,
    )

    # =========================================================
    # MENU DATE OVERRIDES
    # =========================================================

    op.create_table(
        "menu_date_overrides",

        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "chef_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "menu_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "menu_date",
            sa.Date(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["chef_id"],
            ["users.id"],
        ),

        sa.ForeignKeyConstraint(
            ["menu_id"],
            ["menus.id"],
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "chef_id",
            "menu_date",
            name="uq_menu_override_chef_date",
        ),
    )

    op.create_index(
        "idx_menu_override_chef_date",
        "menu_date_overrides",
        ["chef_id", "menu_date"],
        unique=False,
    )

    op.create_index(
        "ix_menu_date_overrides_chef_id",
        "menu_date_overrides",
        ["chef_id"],
        unique=False,
    )

    op.create_index(
        "ix_menu_date_overrides_menu_id",
        "menu_date_overrides",
        ["menu_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # =========================================================
    # REMOVE MENU DATE OVERRIDES
    # =========================================================

    op.drop_index(
        "ix_menu_date_overrides_menu_id",
        table_name="menu_date_overrides",
    )

    op.drop_index(
        "ix_menu_date_overrides_chef_id",
        table_name="menu_date_overrides",
    )

    op.drop_index(
        "idx_menu_override_chef_date",
        table_name="menu_date_overrides",
    )

    op.drop_table("menu_date_overrides")

    # =========================================================
    # REMOVE MENU CYCLE
    # =========================================================

    op.drop_index(
        "ix_menu_cycles_menu_id",
        table_name="menu_cycles",
    )

    op.drop_index(
        "ix_menu_cycles_chef_id",
        table_name="menu_cycles",
    )

    op.drop_index(
        "idx_menu_cycle_chef_day",
        table_name="menu_cycles",
    )

    op.drop_table("menu_cycles")
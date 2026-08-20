"""support multiple menu cycles per chef

Revision ID: e75e8006be57
Revises: 993ff898845a
Create Date: 2026-08-19 13:01:05.840385

"""

from typing import Sequence, Union

from alembic import op


# =========================================================
# REVISION IDENTIFIERS
# =========================================================

revision: str = "e75e8006be57"
down_revision: Union[str, Sequence[str], None] = "993ff898845a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =========================================================
# UPGRADE
# =========================================================

def upgrade() -> None:
    """Upgrade schema."""

    # Remove old constraint:
    # chef_id + cycle_day
    #
    # This allowed only one Day 1, one Day 2, etc.
    # for each chef across the entire database.
    op.drop_constraint(
        "uq_menu_cycle_chef_day",
        "menu_cycles",
        type_="unique",
    )

    # New production constraint:
    #
    # chef + cycle_start_date + cycle_day
    #
    # This allows the same chef to have:
    #
    # Cycle 1 / Day 1
    # Cycle 2 / Day 1
    # Cycle 3 / Day 1
    #
    op.create_unique_constraint(
        "uq_menu_cycle_chef_start_day",
        "menu_cycles",
        [
            "chef_id",
            "cycle_start_date",
            "cycle_day",
        ],
    )

    # Remove old composite index.
    op.drop_index(
        "idx_menu_cycle_chef_day",
        table_name="menu_cycles",
    )

    # Add production composite index.
    op.create_index(
        "idx_menu_cycle_chef_start_day",
        "menu_cycles",
        [
            "chef_id",
            "cycle_start_date",
            "cycle_day",
        ],
        unique=False,
    )


# =========================================================
# DOWNGRADE
# =========================================================

def downgrade() -> None:
    """Downgrade schema."""

    # Remove new index.
    op.drop_index(
        "idx_menu_cycle_chef_start_day",
        table_name="menu_cycles",
    )

    # Restore old index.
    op.create_index(
        "idx_menu_cycle_chef_day",
        "menu_cycles",
        [
            "chef_id",
            "cycle_day",
        ],
        unique=False,
    )

    # Remove new constraint.
    op.drop_constraint(
        "uq_menu_cycle_chef_start_day",
        "menu_cycles",
        type_="unique",
    )

    # Restore old constraint.
    op.create_unique_constraint(
        "uq_menu_cycle_chef_day",
        "menu_cycles",
        [
            "chef_id",
            "cycle_day",
        ],
    )
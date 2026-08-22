"""add meal type to menu cycle

Revision ID: 579db99a5063
Revises: d4fb8ed877ad
Create Date: 2026-08-22 11:43:43.940030
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# =========================================================
# REVISION IDENTIFIERS
# =========================================================

revision: str = "579db99a5063"

down_revision: Union[str, Sequence[str], None] = "d4fb8ed877ad"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# =========================================================
# UPGRADE
# =========================================================

def upgrade() -> None:

    # -----------------------------------------------------
    # 1. ADD meal_type TEMPORARILY NULLABLE
    # -----------------------------------------------------

    op.add_column(
        "menu_cycles",
        sa.Column(
            "meal_type",
            sa.String(),
            nullable=True,
        ),
    )

    # -----------------------------------------------------
    # 2. EXISTING 30-DAY CYCLE DATA
    #
    # Existing records were created before meal_type existed.
    #
    # We cannot safely guess whether an old dish was
    # breakfast/lunch/dinner.
    #
    # Therefore keep existing records temporarily as
    # "legacy".
    #
    # New 90-entry cycles will use:
    # breakfast
    # lunch
    # dinner
    # -----------------------------------------------------

    op.execute(
        """
        UPDATE menu_cycles
        SET meal_type = 'legacy'
        WHERE meal_type IS NULL
        """
    )

    # -----------------------------------------------------
    # 3. MAKE meal_type NOT NULL
    # -----------------------------------------------------

    op.alter_column(
        "menu_cycles",
        "meal_type",
        existing_type=sa.String(),
        nullable=False,
    )

    # -----------------------------------------------------
    # 4. REMOVE OLD UNIQUE CONSTRAINT
    #
    # Old:
    # chef + cycle_start_date + cycle_day
    #
    # This allowed only ONE menu per day.
    #
    # New:
    # chef + cycle_start_date + cycle_day + meal_type
    #
    # This allows:
    # Day 1 breakfast
    # Day 1 lunch
    # Day 1 dinner
    # -----------------------------------------------------

    op.drop_constraint(
        "uq_menu_cycle_chef_start_day",
        "menu_cycles",
        type_="unique",
    )

    # -----------------------------------------------------
    # 5. REMOVE OLD INDEX
    # -----------------------------------------------------

    op.drop_index(
        "idx_menu_cycle_chef_start_day",
        table_name="menu_cycles",
    )

    # -----------------------------------------------------
    # 6. CREATE NEW UNIQUE CONSTRAINT
    # -----------------------------------------------------

    op.create_unique_constraint(
        "uq_menu_cycle_chef_start_day_meal",
        "menu_cycles",
        [
            "chef_id",
            "cycle_start_date",
            "cycle_day",
            "meal_type",
        ],
    )

    # -----------------------------------------------------
    # 7. CREATE NEW COMPOSITE INDEX
    # -----------------------------------------------------

    op.create_index(
        "idx_menu_cycle_chef_start_day_meal",
        "menu_cycles",
        [
            "chef_id",
            "cycle_start_date",
            "cycle_day",
            "meal_type",
        ],
        unique=False,
    )

    # -----------------------------------------------------
    # 8. CREATE meal_type INDEX
    # -----------------------------------------------------

    op.create_index(
        "ix_menu_cycles_meal_type",
        "menu_cycles",
        ["meal_type"],
        unique=False,
    )


# =========================================================
# DOWNGRADE
# =========================================================

def downgrade() -> None:

    # -----------------------------------------------------
    # 1. DROP NEW UNIQUE CONSTRAINT
    # -----------------------------------------------------

    op.drop_constraint(
        "uq_menu_cycle_chef_start_day_meal",
        "menu_cycles",
        type_="unique",
    )

    # -----------------------------------------------------
    # 2. DROP NEW INDEX
    # -----------------------------------------------------

    op.drop_index(
        "idx_menu_cycle_chef_start_day_meal",
        table_name="menu_cycles",
    )

    # -----------------------------------------------------
    # 3. DROP meal_type INDEX
    # -----------------------------------------------------

    op.drop_index(
        "ix_menu_cycles_meal_type",
        table_name="menu_cycles",
    )

    # -----------------------------------------------------
    # 4. RESTORE OLD UNIQUE CONSTRAINT
    # -----------------------------------------------------

    op.create_unique_constraint(
        "uq_menu_cycle_chef_start_day",
        "menu_cycles",
        [
            "chef_id",
            "cycle_start_date",
            "cycle_day",
        ],
    )

    # -----------------------------------------------------
    # 5. RESTORE OLD INDEX
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 6. REMOVE meal_type
    # -----------------------------------------------------

    op.drop_column(
        "menu_cycles",
        "meal_type",
    )
"""add menu date and meal type to cart items

Revision ID: 4e2a64a85163
Revises: 579db99a5063
Create Date: 2026-08-22 15:08:46.627534
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# =========================================================
# REVISION IDENTIFIERS
# =========================================================

revision: str = "4e2a64a85163"

down_revision: Union[str, Sequence[str], None] = "579db99a5063"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# =========================================================
# UPGRADE
# =========================================================

def upgrade() -> None:
    """
    Add menu_date and meal_type to cart_items.

    Only the required cart changes are included here.
    """

    # -----------------------------------------------------
    # MENU DATE
    # -----------------------------------------------------

    op.add_column(
        "cart_items",
        sa.Column(
            "menu_date",
            sa.Date(),
            nullable=True,
        ),
    )

    # -----------------------------------------------------
    # MEAL TYPE
    # -----------------------------------------------------

    op.add_column(
        "cart_items",
        sa.Column(
            "meal_type",
            sa.String(),
            nullable=True,
        ),
    )

    # -----------------------------------------------------
    # INDEXES
    # -----------------------------------------------------

    op.create_index(
        "idx_cartitem_menu_date",
        "cart_items",
        ["menu_id", "menu_date"],
        unique=False,
    )

    op.create_index(
        "idx_cartitem_meal_type",
        "cart_items",
        ["meal_type"],
        unique=False,
    )


# =========================================================
# DOWNGRADE
# =========================================================

def downgrade() -> None:
    """
    Remove menu_date and meal_type from cart_items.
    """

    # -----------------------------------------------------
    # DROP INDEXES
    # -----------------------------------------------------

    op.drop_index(
        "idx_cartitem_meal_type",
        table_name="cart_items",
    )

    op.drop_index(
        "idx_cartitem_menu_date",
        table_name="cart_items",
    )

    # -----------------------------------------------------
    # DROP COLUMNS
    # -----------------------------------------------------

    op.drop_column(
        "cart_items",
        "meal_type",
    )

    op.drop_column(
        "cart_items",
        "menu_date",
    )
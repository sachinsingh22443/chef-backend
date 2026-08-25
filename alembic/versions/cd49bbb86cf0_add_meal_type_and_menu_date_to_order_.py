"""add meal type and menu date to order items

Revision ID: cd49bbb86cf0
Revises: 35f86cd8c578
Create Date: 2026-08-25 12:42:03.114713

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# =========================================================
# REVISION IDENTIFIERS
# =========================================================

revision: str = "cd49bbb86cf0"

down_revision: Union[str, Sequence[str], None] = "35f86cd8c578"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# =========================================================
# UPGRADE
# =========================================================

def upgrade() -> None:

    # =====================================================
    # ADD MEAL TYPE
    # =====================================================

    op.add_column(
        "order_items",
        sa.Column(
            "meal_type",
            sa.String(),
            nullable=True,
        ),
    )

    # =====================================================
    # ADD MENU DATE
    # =====================================================

    op.add_column(
        "order_items",
        sa.Column(
            "menu_date",
            sa.Date(),
            nullable=True,
        ),
    )

    # =====================================================
    # INDEXES
    # =====================================================

    op.create_index(
        "ix_order_items_meal_type",
        "order_items",
        ["meal_type"],
        unique=False,
    )

    op.create_index(
        "ix_order_items_menu_date",
        "order_items",
        ["menu_date"],
        unique=False,
    )

    op.create_index(
        "idx_orderitem_meal_date",
        "order_items",
        ["meal_type", "menu_date"],
        unique=False,
    )


# =========================================================
# DOWNGRADE
# =========================================================

def downgrade() -> None:

    # =====================================================
    # REMOVE INDEXES
    # =====================================================

    op.drop_index(
        "idx_orderitem_meal_date",
        table_name="order_items",
    )

    op.drop_index(
        "ix_order_items_menu_date",
        table_name="order_items",
    )

    op.drop_index(
        "ix_order_items_meal_type",
        table_name="order_items",
    )

    # =====================================================
    # REMOVE COLUMNS
    # =====================================================

    op.drop_column(
        "order_items",
        "menu_date",
    )

    op.drop_column(
        "order_items",
        "meal_type",
    )
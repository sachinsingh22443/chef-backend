"""add tomorrow special pre orders

Revision ID: 42cf77099a95

Revises: cd49bbb86cf0
Create Date: 2026-08-31 19:37:07.743664
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# =========================================================
# REVISION IDENTIFIERS
# =========================================================

revision: str = "42cf77099a95"

down_revision: Union[str, Sequence[str], None] = "cd49bbb86cf0"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# =========================================================
# UPGRADE
# =========================================================

def upgrade() -> None:
    """
    Create Tomorrow Special Pre-Order table.

    IMPORTANT:
    This migration intentionally changes ONLY the new
    tomorrow_special_pre_orders table.
    Existing tables are untouched.
    """

    # =====================================================
    # TOMORROW SPECIAL PRE-ORDERS
    # =====================================================

    op.create_table(
        "tomorrow_special_pre_orders",

        # -------------------------------------------------
        # ID
        # -------------------------------------------------

        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),

        # -------------------------------------------------
        # TOMORROW SPECIAL
        # -------------------------------------------------

        sa.Column(
            "special_id",
            sa.UUID(),
            nullable=False,
        ),

        # -------------------------------------------------
        # ACTUAL ORDER
        # -------------------------------------------------

        sa.Column(
            "order_id",
            sa.UUID(),
            nullable=False,
        ),

        # -------------------------------------------------
        # CUSTOMER
        # -------------------------------------------------

        sa.Column(
            "customer_id",
            sa.UUID(),
            nullable=False,
        ),

        # -------------------------------------------------
        # QUANTITY
        # -------------------------------------------------

        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
        ),

        # -------------------------------------------------
        # PRICE SNAPSHOT
        # -------------------------------------------------

        sa.Column(
            "unit_price",
            sa.Float(),
            nullable=False,
        ),

        sa.Column(
            "total_amount",
            sa.Float(),
            nullable=False,
        ),

        # -------------------------------------------------
        # CREATED AT
        # -------------------------------------------------

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),

        # =================================================
        # FOREIGN KEYS
        # =================================================

        sa.ForeignKeyConstraint(
            ["special_id"],
            ["tomorrow_specials.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),

        # =================================================
        # PRIMARY KEY
        # =================================================

        sa.PrimaryKeyConstraint("id"),
    )

    # =====================================================
    # INDEXES
    # =====================================================

    op.create_index(
        "idx_ts_preorder_special",
        "tomorrow_special_pre_orders",
        ["special_id"],
        unique=False,
    )

    op.create_index(
        "idx_ts_preorder_order",
        "tomorrow_special_pre_orders",
        ["order_id"],
        unique=True,
    )

    op.create_index(
        "idx_ts_preorder_customer",
        "tomorrow_special_pre_orders",
        ["customer_id"],
        unique=False,
    )

    op.create_index(
        "idx_ts_preorder_created",
        "tomorrow_special_pre_orders",
        ["created_at"],
        unique=False,
    )


# =========================================================
# DOWNGRADE
# =========================================================

def downgrade() -> None:
    """
    Remove only Tomorrow Special Pre-Order table.
    """

    # =====================================================
    # DROP INDEXES
    # =====================================================

    op.drop_index(
        "idx_ts_preorder_created",
        table_name="tomorrow_special_pre_orders",
    )

    op.drop_index(
        "idx_ts_preorder_customer",
        table_name="tomorrow_special_pre_orders",
    )

    op.drop_index(
        "idx_ts_preorder_order",
        table_name="tomorrow_special_pre_orders",
    )

    op.drop_index(
        "idx_ts_preorder_special",
        table_name="tomorrow_special_pre_orders",
    )

    # =====================================================
    # DROP TABLE
    # =====================================================

    op.drop_table(
        "tomorrow_special_pre_orders"
    )
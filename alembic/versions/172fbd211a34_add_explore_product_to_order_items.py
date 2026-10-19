
"""add explore product to order items

Revision ID: 172fbd211a34
Revises: 131b5bdb1b49
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# =========================================================
# REVISION IDENTIFIERS
# =========================================================

revision: str = "172fbd211a34"

down_revision: Union[str, Sequence[str], None] = "131b5bdb1b49"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# =========================================================
# UPGRADE
# =========================================================

def upgrade() -> None:
    # Add nullable Explore Product reference.
    # Existing menu and Tomorrow Special order items remain valid.

    op.add_column(
        "order_items",
        sa.Column(
            "product_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # Link order_items.product_id to explore_products.id.
    op.create_foreign_key(
        "fk_order_items_product_id_explore_products",
        "order_items",
        "explore_products",
        ["product_id"],
        ["id"],
    )

    # Index for product lookups.
    op.create_index(
        "ix_order_items_product_id",
        "order_items",
        ["product_id"],
        unique=False,
    )

    # Composite index for order-specific product lookups.
    op.create_index(
        "idx_orderitem_order_product",
        "order_items",
        ["order_id", "product_id"],
        unique=False,
    )


# =========================================================
# DOWNGRADE
# =========================================================

def downgrade() -> None:
    # Remove indexes first.
    op.drop_index(
        "idx_orderitem_order_product",
        table_name="order_items",
    )

    op.drop_index(
        "ix_order_items_product_id",
        table_name="order_items",
    )

    # Remove foreign key.
    op.drop_constraint(
        "fk_order_items_product_id_explore_products",
        "order_items",
        type_="foreignkey",
    )

    # Remove Explore Product reference column.
    op.drop_column(
        "order_items",
        "product_id",
    )



"""add product id to cart items

Revision ID: b3bbd24ced25
Revises: 172fbd211a34
Create Date: 2026-10-20 12:54:19.829956
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3bbd24ced25"
down_revision: Union[str, Sequence[str], None] = "172fbd211a34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add product support to cart_items."""

    # Add nullable product_id so existing cart rows remain valid.
    op.add_column(
        "cart_items",
        sa.Column("product_id", sa.UUID(), nullable=True),
    )

    # Link cart item to Explore Product.
    op.create_foreign_key(
        "fk_cart_items_product_id_explore_products",
        "cart_items",
        "explore_products",
        ["product_id"],
        ["id"],
    )

    # Index for product lookups.
    op.create_index(
        "ix_cart_items_product_id",
        "cart_items",
        ["product_id"],
        unique=False,
    )

    # Composite index for cart and product lookups.
    op.create_index(
        "idx_cartitem_cart_product",
        "cart_items",
        ["cart_id", "product_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove Explore Product support from cart_items."""

    op.drop_index(
        "idx_cartitem_cart_product",
        table_name="cart_items",
    )

    op.drop_index(
        "ix_cart_items_product_id",
        table_name="cart_items",
    )

    op.drop_constraint(
        "fk_cart_items_product_id_explore_products",
        "cart_items",
        type_="foreignkey",
    )

    op.drop_column(
        "cart_items",
        "product_id",
    )

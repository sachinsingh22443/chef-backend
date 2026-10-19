
"""create explore products table

Revision ID: 131b5bdb1b49
Revises: 334e1721f915
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers
revision: str = "131b5bdb1b49"
down_revision: Union[str, Sequence[str], None] = "334e1721f915"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create only the Explore products table.
    op.create_table(
        "explore_products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "chef_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["chef_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_explore_product_category_active",
        "explore_products",
        ["category", "is_active"],
        unique=False,
    )
    op.create_index(
        "idx_explore_product_chef_active",
        "explore_products",
        ["chef_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_explore_products_category",
        "explore_products",
        ["category"],
        unique=False,
    )
    op.create_index(
        "ix_explore_products_chef_id",
        "explore_products",
        ["chef_id"],
        unique=False,
    )
    op.create_index(
        "ix_explore_products_is_active",
        "explore_products",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_explore_products_name",
        "explore_products",
        ["name"],
        unique=False,
    )


def downgrade() -> None:
    # Remove only the Explore products table and its indexes.
    op.drop_index(
        "ix_explore_products_name",
        table_name="explore_products",
    )
    op.drop_index(
        "ix_explore_products_is_active",
        table_name="explore_products",
    )
    op.drop_index(
        "ix_explore_products_chef_id",
        table_name="explore_products",
    )
    op.drop_index(
        "ix_explore_products_category",
        table_name="explore_products",
    )
    op.drop_index(
        "idx_explore_product_chef_active",
        table_name="explore_products",
    )
    op.drop_index(
        "idx_explore_product_category_active",
        table_name="explore_products",
    )
    op.drop_table("explore_products")

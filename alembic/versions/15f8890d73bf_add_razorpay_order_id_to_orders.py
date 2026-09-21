"""add razorpay order id to orders

Revision ID: 15f8890d73bf
Revises: 7b81e8258bdc
Create Date: 2026-09-20 23:32:06.786830

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "15f8890d73bf"
down_revision: Union[str, Sequence[str], None] = "7b81e8258bdc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "orders",
        sa.Column(
            "razorpay_order_id",
            sa.String(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_orders_razorpay_order_id",
        "orders",
        ["razorpay_order_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_orders_razorpay_order_id",
        table_name="orders",
    )

    op.drop_column(
        "orders",
        "razorpay_order_id",
    )
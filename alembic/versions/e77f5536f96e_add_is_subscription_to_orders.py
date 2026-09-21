"""add is subscription to orders

Revision ID: e77f5536f96e
Revises: 15f8890d73bf
Create Date: 2026-09-20 23:53:26.201118
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e77f5536f96e"
down_revision: Union[str, Sequence[str], None] = "15f8890d73bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "is_subscription",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_index(
        "ix_orders_is_subscription",
        "orders",
        ["is_subscription"],
        unique=False,
    )

    op.alter_column(
        "orders",
        "is_subscription",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_orders_is_subscription",
        table_name="orders",
    )

    op.drop_column(
        "orders",
        "is_subscription",
    )
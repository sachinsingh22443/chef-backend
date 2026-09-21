"""add order id to subscriptions

Revision ID: 094f8c9bcebb
Revises: 15f8890d73bf
Create Date: 2026-09-20 23:42:35.904312

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "094f8c9bcebb"
down_revision: Union[str, Sequence[str], None] = "15f8890d73bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "subscriptions",
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_subscriptions_order_id_orders",
        "subscriptions",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_subscriptions_order_id",
        "subscriptions",
        ["order_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_subscriptions_order_id",
        table_name="subscriptions",
    )

    op.drop_constraint(
        "fk_subscriptions_order_id_orders",
        "subscriptions",
        type_="foreignkey",
    )

    op.drop_column(
        "subscriptions",
        "order_id",
    )
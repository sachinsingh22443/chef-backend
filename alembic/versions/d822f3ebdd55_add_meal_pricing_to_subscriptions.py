"""add meal pricing to subscriptions

Revision ID: d822f3ebdd55
Revises: 8b851a78a86d
Create Date: 2026-08-09 19:26:08.009383

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d822f3ebdd55"
down_revision: Union[str, Sequence[str], None] = "8b851a78a86d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add meal price snapshot to daily subscription meal schedule.
    op.add_column(
        "subscription_meal_schedule",
        sa.Column(
            "meal_price",
            sa.Float(),
            nullable=True,
        ),
    )

    # Add meal pricing to subscription plans.
    op.add_column(
        "subscription_plans",
        sa.Column(
            "lunch_price",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "subscription_plans",
        sa.Column(
            "dinner_price",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "subscription_plans",
        "dinner_price",
    )

    op.drop_column(
        "subscription_plans",
        "lunch_price",
    )

    op.drop_column(
        "subscription_meal_schedule",
        "meal_price",
    )
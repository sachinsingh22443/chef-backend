"""add breakfast subscription fields

Revision ID: dafbfe235676
Revises: b2c71bd9c34e
Create Date: 2026-08-08 12:26:10.778015
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "dafbfe235676"
down_revision: Union[str, Sequence[str], None] = "b2c71bd9c34e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "subscription_plans",
        sa.Column(
            "breakfast_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "subscription_plans",
        sa.Column(
            "breakfast_price",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "subscriptions",
        sa.Column(
            "breakfast_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "subscriptions",
        sa.Column(
            "breakfast_price",
            sa.Float(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "subscriptions",
        "breakfast_price",
    )

    op.drop_column(
        "subscriptions",
        "breakfast_enabled",
    )

    op.drop_column(
        "subscription_plans",
        "breakfast_price",
    )

    op.drop_column(
        "subscription_plans",
        "breakfast_available",
    )

"""add subscription meal schedule

Revision ID: 81a78d6a578f
Revises: dafbfe235676
Create Date: 2026-08-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "81a78d6a578f"
down_revision: Union[str, Sequence[str], None] = "dafbfe235676"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "subscription_meal_schedule",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "date",
            sa.Date(),
            nullable=False,
        ),

        sa.Column(
            "meal_type",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="on",
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "subscription_id",
            "date",
            "meal_type",
            name="uq_subscription_meal_date",
        ),
    )

    op.create_index(
        "idx_subscription_meal_date",
        "subscription_meal_schedule",
        ["subscription_id", "date"],
        unique=False,
    )

    op.create_index(
        "ix_subscription_meal_schedule_date",
        "subscription_meal_schedule",
        ["date"],
        unique=False,
    )

    op.create_index(
        "ix_subscription_meal_schedule_subscription_id",
        "subscription_meal_schedule",
        ["subscription_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_subscription_meal_schedule_subscription_id",
        table_name="subscription_meal_schedule",
    )

    op.drop_index(
        "ix_subscription_meal_schedule_date",
        table_name="subscription_meal_schedule",
    )

    op.drop_index(
        "idx_subscription_meal_date",
        table_name="subscription_meal_schedule",
    )

    op.drop_table("subscription_meal_schedule")
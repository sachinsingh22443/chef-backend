"""add meal cutoff time

Revision ID: 417d1af7c5c6
Revises: 81a78d6a578f
Create Date: 2026-08-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "417d1af7c5c6"
down_revision: Union[str, Sequence[str], None] = "81a78d6a578f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "subscription_meal_schedule",
        sa.Column(
            "cutoff_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "subscription_meal_schedule",
        "cutoff_at",
    )
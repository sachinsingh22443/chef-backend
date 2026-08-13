"""add premium tomorrow special fields

Revision ID: 96a041a7a03d
Revises: d822f3ebdd55
Create Date: 2026-08-13 13:00:24.792538

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "96a041a7a03d"
down_revision: Union[str, Sequence[str], None] = "d822f3ebdd55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ==========================================
    # TOMORROW SPECIAL - PREMIUM FIELDS
    # ==========================================

    op.add_column(
        "tomorrow_specials",
        sa.Column(
            "original_price",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "tomorrow_specials",
        sa.Column(
            "calories",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "tomorrow_specials",
        sa.Column(
            "protein",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "tomorrow_specials",
        sa.Column(
            "carbs",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "tomorrow_specials",
        sa.Column(
            "fats",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "tomorrow_specials",
        sa.Column(
            "preparation_time",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "tomorrow_specials",
        sa.Column(
            "ingredients",
            sa.String(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    # ==========================================
    # REMOVE TOMORROW SPECIAL PREMIUM FIELDS
    # ==========================================

    op.drop_column(
        "tomorrow_specials",
        "ingredients",
    )

    op.drop_column(
        "tomorrow_specials",
        "preparation_time",
    )

    op.drop_column(
        "tomorrow_specials",
        "fats",
    )

    op.drop_column(
        "tomorrow_specials",
        "carbs",
    )

    op.drop_column(
        "tomorrow_specials",
        "protein",
    )

    op.drop_column(
        "tomorrow_specials",
        "calories",
    )

    op.drop_column(
        "tomorrow_specials",
        "original_price",
    )
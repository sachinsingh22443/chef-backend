"""add special date to tomorrow specials

Revision ID: e3b06754b73e
Revises: 96a041a7a03d
Create Date: 2026-08-14 13:35:32.975876

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3b06754b73e"
down_revision: Union[str, Sequence[str], None] = "96a041a7a03d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # =============================
    # 📅 ADD SPECIAL DATE
    # =============================

    op.add_column(
        "tomorrow_specials",
        sa.Column(
            "special_date",
            sa.Date(),
            nullable=True,
        ),
    )

    # =============================
    # 🔄 BACKFILL EXISTING RECORDS
    # =============================
    #
    # Existing Tomorrow Specials ko
    # unke created_at ki date di jayegi.
    #
    op.execute(
        """
        UPDATE tomorrow_specials
        SET special_date = created_at::date
        WHERE special_date IS NULL
        """
    )

    # =============================
    # 🔒 MAKE COLUMN REQUIRED
    # =============================

    op.alter_column(
        "tomorrow_specials",
        "special_date",
        existing_type=sa.Date(),
        nullable=False,
    )

    # =============================
    # ⚡ INDEX
    # =============================

    op.create_index(
        "ix_tomorrow_specials_special_date",
        "tomorrow_specials",
        ["special_date"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # =============================
    # ❌ REMOVE INDEX
    # =============================

    op.drop_index(
        "ix_tomorrow_specials_special_date",
        table_name="tomorrow_specials",
    )

    # =============================
    # ❌ REMOVE COLUMN
    # =============================

    op.drop_column(
        "tomorrow_specials",
        "special_date",
    )
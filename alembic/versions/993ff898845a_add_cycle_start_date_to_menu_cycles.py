"""add cycle start date to menu cycles

Revision ID: 993ff898845a
Revises: 90e453b9b2ab
Create Date: 2026-08-19 12:51:55.584984

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# =========================================================
# REVISION IDENTIFIERS
# =========================================================

revision: str = "993ff898845a"
down_revision: Union[str, Sequence[str], None] = "90e453b9b2ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =========================================================
# UPGRADE
# =========================================================

def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "menu_cycles",
        sa.Column(
            "cycle_start_date",
            sa.Date(),
            nullable=False,
        ),
    )


# =========================================================
# DOWNGRADE
# =========================================================

def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "menu_cycles",
        "cycle_start_date",
    )
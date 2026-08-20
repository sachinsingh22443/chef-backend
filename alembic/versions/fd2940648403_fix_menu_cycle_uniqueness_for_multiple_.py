"""fix menu cycle uniqueness for multiple cycles

Revision ID: fd2940648403
Revises: e75e8006be57
Create Date: 2026-08-19 13:46:57.842996
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "fd2940648403"
down_revision: Union[str, Sequence[str], None] = "e75e8006be57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    The required MenuCycle uniqueness/index structure
    is already present in the database.

    Current database structure:

        UNIQUE (
            chef_id,
            cycle_start_date,
            cycle_day
        )

        INDEX (
            chef_id,
            cycle_start_date,
            cycle_day
        )

    Therefore no additional DDL is required here.
    """

    pass


def downgrade() -> None:
    """
    No database change was performed by this migration,
    therefore there is nothing to downgrade.
    """

    pass
"""merge migration heads

Revision ID: c6c5123851b9
Revises: 094f8c9bcebb, e77f5536f96e
Create Date: 2026-09-28 22:07:09.749547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6c5123851b9'
down_revision: Union[str, Sequence[str], None] = ('094f8c9bcebb', 'e77f5536f96e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass


"""add fcm device tokens

Revision ID: 334e1721f915
Revises: add_delivery_tracking_001
Create Date: 2026-10-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers
revision: str = "334e1721f915"
down_revision: Union[str, Sequence[str], None] = "add_delivery_tracking_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the FCM device tokens table."""

    op.create_table(
        "fcm_device_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "token",
            sa.String(),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_fcm_device_tokens_user_id",
        "fcm_device_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the FCM device tokens table."""

    op.drop_index(
        "ix_fcm_device_tokens_user_id",
        table_name="fcm_device_tokens",
    )

    op.drop_table("fcm_device_tokens")

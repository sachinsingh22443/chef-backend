"""create delivery batch pickups

Revision ID: 6e9919a4899d
Revises: a2db648940d5

Create Date: 2026-10-02 00:00:49.946769

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# ============================================================
# REVISION IDENTIFIERS
# ============================================================

revision: str = "6e9919a4899d"

down_revision: Union[str, Sequence[str], None] = "a2db648940d5"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# ============================================================
# UPGRADE
# ============================================================

def upgrade() -> None:

    op.create_table(
        "delivery_batch_pickups",

        # ----------------------------------------------------
        # PRIMARY KEY
        # ----------------------------------------------------

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        # ----------------------------------------------------
        # DELIVERY BATCH
        # ----------------------------------------------------

        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        # ----------------------------------------------------
        # CHEF
        # ----------------------------------------------------

        sa.Column(
            "chef_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        # ----------------------------------------------------
        # PICKUP SEQUENCE
        # ----------------------------------------------------

        sa.Column(
            "sequence_no",
            sa.Integer(),
            nullable=False,
        ),

        # ----------------------------------------------------
        # CHEF SNAPSHOT
        # ----------------------------------------------------

        sa.Column(
            "chef_name",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "kitchen_location",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "latitude",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "longitude",
            sa.Float(),
            nullable=True,
        ),

        # ----------------------------------------------------
        # TIFFIN QUANTITY
        # ----------------------------------------------------

        sa.Column(
            "expected_tiffins",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "received_tiffins",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        # ----------------------------------------------------
        # PICKUP STATUS
        # ----------------------------------------------------

        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),

        # ----------------------------------------------------
        # TIMESTAMPS
        # ----------------------------------------------------

        sa.Column(
            "arrived_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "picked_up_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),

        # ----------------------------------------------------
        # FOREIGN KEYS
        # ----------------------------------------------------

        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["delivery_batches.id"],
        ),

        sa.ForeignKeyConstraint(
            ["chef_id"],
            ["users.id"],
        ),

        # ----------------------------------------------------
        # PRIMARY KEY
        # ----------------------------------------------------

        sa.PrimaryKeyConstraint("id"),
    )

    # ========================================================
    # INDEXES
    # ========================================================

    op.create_index(
        "idx_delivery_pickup_batch_sequence",
        "delivery_batch_pickups",
        ["batch_id", "sequence_no"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_pickup_batch_status",
        "delivery_batch_pickups",
        ["batch_id", "status"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_pickup_chef",
        "delivery_batch_pickups",
        ["chef_id"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_pickup_location",
        "delivery_batch_pickups",
        ["latitude", "longitude"],
        unique=False,
    )


# ============================================================
# DOWNGRADE
# ============================================================

def downgrade() -> None:

    op.drop_index(
        "idx_delivery_pickup_location",
        table_name="delivery_batch_pickups",
    )

    op.drop_index(
        "idx_delivery_pickup_chef",
        table_name="delivery_batch_pickups",
    )

    op.drop_index(
        "idx_delivery_pickup_batch_status",
        table_name="delivery_batch_pickups",
    )

    op.drop_index(
        "idx_delivery_pickup_batch_sequence",
        table_name="delivery_batch_pickups",
    )

    op.drop_table(
        "delivery_batch_pickups",
    )
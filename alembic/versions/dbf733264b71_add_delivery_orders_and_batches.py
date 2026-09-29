"""add delivery orders and batches

Revision ID: dbf733264b71
Revises: c6c5123851b9
Create Date: 2026-09-28 22:10:28.901663
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "dbf733264b71"
down_revision: Union[str, Sequence[str], None] = "c6c5123851b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create delivery system tables only."""

    # ============================================================
    # DELIVERY BATCHES
    # ============================================================

    op.create_table(
        "delivery_batches",

        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "delivery_partner_id",
            sa.UUID(),
            nullable=True,
        ),

        sa.Column(
            "delivery_date",
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
            server_default="created",
        ),

        sa.Column(
            "total_orders",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "total_tiffins",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "start_latitude",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "start_longitude",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),

        sa.Column(
            "assigned_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "completed_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["delivery_partner_id"],
            ["users.id"],
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    # Delivery batch indexes
    op.create_index(
        "idx_delivery_batch_date_meal",
        "delivery_batches",
        ["delivery_date", "meal_type"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_batch_date_status",
        "delivery_batches",
        ["delivery_date", "status"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_batch_partner_status",
        "delivery_batches",
        ["delivery_partner_id", "status"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_batches_created_at",
        "delivery_batches",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_batches_delivery_date",
        "delivery_batches",
        ["delivery_date"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_batches_delivery_partner_id",
        "delivery_batches",
        ["delivery_partner_id"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_batches_meal_type",
        "delivery_batches",
        ["meal_type"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_batches_status",
        "delivery_batches",
        ["status"],
        unique=False,
    )

    # ============================================================
    # DELIVERY ORDERS
    # ============================================================

    op.create_table(
        "delivery_orders",

        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "order_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "customer_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "customer_name",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "customer_phone",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "address_snapshot",
            sa.String(),
            nullable=False,
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

        sa.Column(
            "meal_type",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "total_tiffins",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "delivery_partner_id",
            sa.UUID(),
            nullable=True,
        ),

        sa.Column(
            "batch_id",
            sa.UUID(),
            nullable=True,
        ),

        sa.Column(
            "delivery_status",
            sa.String(),
            nullable=False,
            server_default="waiting",
        ),

        sa.Column(
            "sequence_no",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "assigned_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "picked_up_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "delivered_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),

        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["delivery_batches.id"],
        ),

        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
        ),

        sa.ForeignKeyConstraint(
            ["delivery_partner_id"],
            ["users.id"],
        ),

        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "order_id",
            name="uq_delivery_orders_order_id",
        ),
    )

    # Delivery order indexes
    op.create_index(
        "idx_delivery_order_batch_sequence",
        "delivery_orders",
        ["batch_id", "sequence_no"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_order_customer_status",
        "delivery_orders",
        ["customer_id", "delivery_status"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_order_location",
        "delivery_orders",
        ["latitude", "longitude"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_order_meal_status",
        "delivery_orders",
        ["meal_type", "delivery_status"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_order_partner_status",
        "delivery_orders",
        ["delivery_partner_id", "delivery_status"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_orders_batch_id",
        "delivery_orders",
        ["batch_id"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_orders_created_at",
        "delivery_orders",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_orders_customer_id",
        "delivery_orders",
        ["customer_id"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_orders_customer_phone",
        "delivery_orders",
        ["customer_phone"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_orders_delivery_partner_id",
        "delivery_orders",
        ["delivery_partner_id"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_orders_delivery_status",
        "delivery_orders",
        ["delivery_status"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_orders_meal_type",
        "delivery_orders",
        ["meal_type"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_orders_order_id",
        "delivery_orders",
        ["order_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove delivery system tables."""

    # Drop delivery_orders indexes
    op.drop_index(
        "ix_delivery_orders_order_id",
        table_name="delivery_orders",
    )

    op.drop_index(
        "ix_delivery_orders_meal_type",
        table_name="delivery_orders",
    )

    op.drop_index(
        "ix_delivery_orders_delivery_status",
        table_name="delivery_orders",
    )

    op.drop_index(
        "ix_delivery_orders_delivery_partner_id",
        table_name="delivery_orders",
    )

    op.drop_index(
        "ix_delivery_orders_customer_phone",
        table_name="delivery_orders",
    )

    op.drop_index(
        "ix_delivery_orders_customer_id",
        table_name="delivery_orders",
    )

    op.drop_index(
        "ix_delivery_orders_created_at",
        table_name="delivery_orders",
    )

    op.drop_index(
        "ix_delivery_orders_batch_id",
        table_name="delivery_orders",
    )

    op.drop_index(
        "idx_delivery_order_partner_status",
        table_name="delivery_orders",
    )

    op.drop_index(
        "idx_delivery_order_meal_status",
        table_name="delivery_orders",
    )

    op.drop_index(
        "idx_delivery_order_location",
        table_name="delivery_orders",
    )

    op.drop_index(
        "idx_delivery_order_customer_status",
        table_name="delivery_orders",
    )

    op.drop_index(
        "idx_delivery_order_batch_sequence",
        table_name="delivery_orders",
    )

    op.drop_table("delivery_orders")

    # Drop delivery_batches indexes
    op.drop_index(
        "ix_delivery_batches_status",
        table_name="delivery_batches",
    )

    op.drop_index(
        "ix_delivery_batches_meal_type",
        table_name="delivery_batches",
    )

    op.drop_index(
        "ix_delivery_batches_delivery_partner_id",
        table_name="delivery_batches",
    )

    op.drop_index(
        "ix_delivery_batches_delivery_date",
        table_name="delivery_batches",
    )

    op.drop_index(
        "ix_delivery_batches_created_at",
        table_name="delivery_batches",
    )

    op.drop_index(
        "idx_delivery_batch_partner_status",
        table_name="delivery_batches",
    )

    op.drop_index(
        "idx_delivery_batch_date_status",
        table_name="delivery_batches",
    )

    op.drop_index(
        "idx_delivery_batch_date_meal",
        table_name="delivery_batches",
    )

    op.drop_table("delivery_batches")
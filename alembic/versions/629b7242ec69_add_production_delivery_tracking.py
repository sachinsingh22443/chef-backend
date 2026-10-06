"""add production delivery tracking

Revision ID: add_delivery_tracking_001
Revises: 6e9919a4899d
Create Date: 2026-10-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# ============================================================
# REVISION IDENTIFIERS
# ============================================================

revision: str = "add_delivery_tracking_001"
down_revision: Union[str, Sequence[str], None] = "6e9919a4899d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ============================================================
# UPGRADE
# ============================================================

def upgrade() -> None:

    # ========================================================
    # 1. DELIVERY COD COLLECTIONS
    # ========================================================

    op.create_table(
        "delivery_cod_collections",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "delivery_order_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "delivery_partner_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),

        sa.Column(
            "order_amount",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "collected_amount",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "payment_status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),

        sa.Column(
            "collection_method",
            sa.String(length=30),
            nullable=True,
        ),

        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "collected_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.ForeignKeyConstraint(
            ["delivery_order_id"],
            ["delivery_orders.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["delivery_partner_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.UniqueConstraint(
            "delivery_order_id",
            name="uq_delivery_cod_delivery_order",
        ),
    )

    op.create_index(
        "idx_delivery_cod_order_status",
        "delivery_cod_collections",
        ["order_id", "payment_status"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_cod_partner_status",
        "delivery_cod_collections",
        ["delivery_partner_id", "payment_status"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_cod_collected_at",
        "delivery_cod_collections",
        ["collected_at"],
        unique=False,
    )


    # ========================================================
    # 2. DELIVERY ORDER EVENTS
    # ========================================================

    op.create_table(
        "delivery_order_events",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "delivery_order_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "event_type",
            sa.String(length=50),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=50),
            nullable=True,
        ),

        sa.Column(
            "description",
            sa.Text(),
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

        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.ForeignKeyConstraint(
            ["delivery_order_id"],
            ["delivery_orders.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "idx_delivery_event_order_created",
        "delivery_order_events",
        ["delivery_order_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_event_order_type",
        "delivery_order_events",
        ["delivery_order_id", "event_type"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_event_order_status",
        "delivery_order_events",
        ["order_id", "status"],
        unique=False,
    )


    # ========================================================
    # 3. DELIVERY ORDER ISSUES
    # ========================================================

    op.create_table(
        "delivery_order_issues",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "delivery_order_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "reported_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),

        sa.Column(
            "issue_type",
            sa.String(length=50),
            nullable=False,
        ),

        sa.Column(
            "reason",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="open",
        ),

        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.Column(
            "resolved_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["delivery_order_id"],
            ["delivery_orders.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["reported_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "idx_delivery_issue_order_status",
        "delivery_order_issues",
        ["delivery_order_id", "status"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_issue_type_status",
        "delivery_order_issues",
        ["issue_type", "status"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_issue_created",
        "delivery_order_issues",
        ["created_at"],
        unique=False,
    )


    # ========================================================
    # 4. DELIVERY PROOFS
    # ========================================================

    op.create_table(
        "delivery_proofs",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "delivery_order_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "delivery_partner_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),

        sa.Column(
            "verification_type",
            sa.String(length=30),
            nullable=False,
            server_default="manual",
        ),

        sa.Column(
            "otp_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),

        sa.Column(
            "photo_url",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "verified_at",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.ForeignKeyConstraint(
            ["delivery_order_id"],
            ["delivery_orders.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["delivery_partner_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.UniqueConstraint(
            "delivery_order_id",
            name="uq_delivery_proof_delivery_order",
        ),
    )

    op.create_index(
        "idx_delivery_proof_partner",
        "delivery_proofs",
        ["delivery_partner_id"],
        unique=False,
    )

    op.create_index(
        "idx_delivery_proof_verified",
        "delivery_proofs",
        ["otp_verified", "verified_at"],
        unique=False,
    )


# ============================================================
# DOWNGRADE
# ============================================================

def downgrade() -> None:

    op.drop_index(
        "idx_delivery_proof_verified",
        table_name="delivery_proofs",
    )

    op.drop_index(
        "idx_delivery_proof_partner",
        table_name="delivery_proofs",
    )

    op.drop_table("delivery_proofs")


    op.drop_index(
        "idx_delivery_issue_created",
        table_name="delivery_order_issues",
    )

    op.drop_index(
        "idx_delivery_issue_type_status",
        table_name="delivery_order_issues",
    )

    op.drop_index(
        "idx_delivery_issue_order_status",
        table_name="delivery_order_issues",
    )

    op.drop_table("delivery_order_issues")


    op.drop_index(
        "idx_delivery_event_order_status",
        table_name="delivery_order_events",
    )

    op.drop_index(
        "idx_delivery_event_order_type",
        table_name="delivery_order_events",
    )

    op.drop_index(
        "idx_delivery_event_order_created",
        table_name="delivery_order_events",
    )

    op.drop_table("delivery_order_events")


    op.drop_index(
        "idx_delivery_cod_collected_at",
        table_name="delivery_cod_collections",
    )

    op.drop_index(
        "idx_delivery_cod_partner_status",
        table_name="delivery_cod_collections",
    )

    op.drop_index(
        "idx_delivery_cod_order_status",
        table_name="delivery_cod_collections",
    )

    op.drop_table("delivery_cod_collections")
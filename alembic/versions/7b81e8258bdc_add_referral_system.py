"""add referral system

Revision ID: 7b81e8258bdc
Revises: 42cf77099a95
Create Date: 2026-09-20 22:42:19.566255

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b81e8258bdc"
down_revision: Union[str, Sequence[str], None] = "42cf77099a95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ============================================================
    # 1. USERS - REFERRAL FIELDS
    # ============================================================

    op.add_column(
        "users",
        sa.Column(
            "referral_code",
            sa.String(length=20),
            nullable=True,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "referred_by",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_users_referral_code",
        "users",
        ["referral_code"],
        unique=True,
    )

    op.create_index(
        "ix_users_referred_by",
        "users",
        ["referred_by"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_users_referred_by_users",
        "users",
        "users",
        ["referred_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # ============================================================
    # 2. REFERRALS TABLE
    # ============================================================

    op.create_table(
        "referrals",

        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "referrer_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "referred_user_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "referral_code",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING",
        ),

        sa.Column(
            "reward_amount",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),

        sa.Column(
            "reward_type",
            sa.String(length=50),
            nullable=True,
        ),

        sa.Column(
            "order_id",
            sa.UUID(),
            nullable=True,
        ),

        sa.Column(
            "subscription_id",
            sa.UUID(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.Column(
            "rewarded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "cancellation_reason",
            sa.String(),
            nullable=True,
        ),

        # -------------------------
        # Primary Key
        # -------------------------

        sa.PrimaryKeyConstraint("id"),

        # -------------------------
        # Foreign Keys
        # -------------------------

        sa.ForeignKeyConstraint(
            ["referrer_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["referred_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            ondelete="SET NULL",
        ),

        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="SET NULL",
        ),

        # -------------------------
        # Anti-duplicate protection
        # -------------------------

        sa.UniqueConstraint(
            "referred_user_id",
            name="uq_referral_referred_user",
        ),

        sa.UniqueConstraint(
            "referrer_id",
            "referred_user_id",
            name="uq_referral_referrer_referred",
        ),
    )

    # ============================================================
    # 3. REFERRAL INDEXES
    # ============================================================

    op.create_index(
        "idx_referral_referrer_status",
        "referrals",
        ["referrer_id", "status"],
        unique=False,
    )

    op.create_index(
        "ix_referrals_referrer_id",
        "referrals",
        ["referrer_id"],
        unique=False,
    )

    op.create_index(
        "ix_referrals_referred_user_id",
        "referrals",
        ["referred_user_id"],
        unique=True,
    )

    op.create_index(
        "ix_referrals_referral_code",
        "referrals",
        ["referral_code"],
        unique=False,
    )

    op.create_index(
        "ix_referrals_order_id",
        "referrals",
        ["order_id"],
        unique=False,
    )

    op.create_index(
        "ix_referrals_subscription_id",
        "referrals",
        ["subscription_id"],
        unique=False,
    )

    op.create_index(
        "ix_referrals_status",
        "referrals",
        ["status"],
        unique=False,
    )

    # ============================================================
    # 4. WALLET TRANSACTIONS - REFERRAL SUPPORT
    # ============================================================

    op.add_column(
        "wallet_transactions",
        sa.Column(
            "order_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.add_column(
        "wallet_transactions",
        sa.Column(
            "referral_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_wallet_transactions_order_id",
        "wallet_transactions",
        ["order_id"],
        unique=False,
    )

    op.create_index(
        "ix_wallet_transactions_referral_id",
        "wallet_transactions",
        ["referral_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_wallet_transactions_order_id_orders",
        "wallet_transactions",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_foreign_key(
        "fk_wallet_transactions_referral_id_referrals",
        "wallet_transactions",
        "referrals",
        ["referral_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""

    # ============================================================
    # 1. WALLET TRANSACTIONS
    # ============================================================

    op.drop_constraint(
        "fk_wallet_transactions_referral_id_referrals",
        "wallet_transactions",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_wallet_transactions_order_id_orders",
        "wallet_transactions",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_wallet_transactions_referral_id",
        table_name="wallet_transactions",
    )

    op.drop_index(
        "ix_wallet_transactions_order_id",
        table_name="wallet_transactions",
    )

    op.drop_column(
        "wallet_transactions",
        "referral_id",
    )

    op.drop_column(
        "wallet_transactions",
        "order_id",
    )

    # ============================================================
    # 2. REFERRALS TABLE
    # ============================================================

    op.drop_index(
        "ix_referrals_status",
        table_name="referrals",
    )

    op.drop_index(
        "ix_referrals_subscription_id",
        table_name="referrals",
    )

    op.drop_index(
        "ix_referrals_order_id",
        table_name="referrals",
    )

    op.drop_index(
        "ix_referrals_referral_code",
        table_name="referrals",
    )

    op.drop_index(
        "ix_referrals_referred_user_id",
        table_name="referrals",
    )

    op.drop_index(
        "ix_referrals_referrer_id",
        table_name="referrals",
    )

    op.drop_index(
        "idx_referral_referrer_status",
        table_name="referrals",
    )

    op.drop_table(
        "referrals",
    )

    # ============================================================
    # 3. USERS
    # ============================================================

    op.drop_constraint(
        "fk_users_referred_by_users",
        "users",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_users_referred_by",
        table_name="users",
    )

    op.drop_index(
        "ix_users_referral_code",
        table_name="users",
    )

    op.drop_column(
        "users",
        "referred_by",
    )

    op.drop_column(
        "users",
        "referral_code",
    )
"""add customer wallet

Revision ID: 8b851a78a86d
Revises: 417d1af7c5c6
Create Date: 2026-08-08 19:36:34.303701

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8b851a78a86d"
down_revision: Union[str, Sequence[str], None] = "417d1af7c5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # =========================================================
    # CUSTOMER WALLET
    # =========================================================

    op.create_table(
        "wallets",

        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "balance",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "user_id",
            name="uq_wallet_user_id",
        ),
    )

    # Wallet indexes

    op.create_index(
        "idx_wallet_user_balance",
        "wallets",
        ["user_id", "balance"],
        unique=False,
    )

    op.create_index(
        op.f("ix_wallets_user_id"),
        "wallets",
        ["user_id"],
        unique=True,
    )

    # =========================================================
    # WALLET TRANSACTIONS
    # =========================================================

    op.create_table(
        "wallet_transactions",

        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "wallet_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
        ),

        sa.Column(
            "amount",
            sa.Float(),
            nullable=False,
        ),

        sa.Column(
            "transaction_type",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "meal_type",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "subscription_id",
            sa.UUID(),
            nullable=True,
        ),

        sa.Column(
            "schedule_id",
            sa.UUID(),
            nullable=True,
        ),

        sa.Column(
            "description",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # -----------------------------------------------------
        # FOREIGN KEYS
        # -----------------------------------------------------

        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="SET NULL",
        ),

        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["subscription_meal_schedule.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    # =========================================================
    # WALLET TRANSACTION INDEXES
    # =========================================================

    op.create_index(
        "idx_wallet_tx_subscription_meal",
        "wallet_transactions",
        ["subscription_id", "meal_type"],
        unique=False,
    )

    op.create_index(
        "idx_wallet_tx_user_created",
        "wallet_transactions",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_index(
        op.f("ix_wallet_transactions_created_at"),
        "wallet_transactions",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        op.f("ix_wallet_transactions_schedule_id"),
        "wallet_transactions",
        ["schedule_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_wallet_transactions_subscription_id"),
        "wallet_transactions",
        ["subscription_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_wallet_transactions_user_id"),
        "wallet_transactions",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_wallet_transactions_wallet_id"),
        "wallet_transactions",
        ["wallet_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # =========================================================
    # REMOVE WALLET TRANSACTION INDEXES
    # =========================================================

    op.drop_index(
        op.f("ix_wallet_transactions_wallet_id"),
        table_name="wallet_transactions",
    )

    op.drop_index(
        op.f("ix_wallet_transactions_user_id"),
        table_name="wallet_transactions",
    )

    op.drop_index(
        op.f("ix_wallet_transactions_subscription_id"),
        table_name="wallet_transactions",
    )

    op.drop_index(
        op.f("ix_wallet_transactions_schedule_id"),
        table_name="wallet_transactions",
    )

    op.drop_index(
        op.f("ix_wallet_transactions_created_at"),
        table_name="wallet_transactions",
    )

    op.drop_index(
        "idx_wallet_tx_user_created",
        table_name="wallet_transactions",
    )

    op.drop_index(
        "idx_wallet_tx_subscription_meal",
        table_name="wallet_transactions",
    )

    # Remove wallet transactions table

    op.drop_table("wallet_transactions")

    # =========================================================
    # REMOVE WALLET
    # =========================================================

    op.drop_index(
        op.f("ix_wallets_user_id"),
        table_name="wallets",
    )

    op.drop_index(
        "idx_wallet_user_balance",
        table_name="wallets",
    )

    op.drop_table("wallets")
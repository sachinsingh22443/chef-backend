"""add menu to subscription meal schedule

Revision ID: d4fb8ed877ad
Revises: fd2940648403
Create Date: 2026-08-19 19:29:28.584705

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# =========================================================
# REVISION IDENTIFIERS
# =========================================================

revision: str = "d4fb8ed877ad"
down_revision: Union[str, Sequence[str], None] = "fd2940648403"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =========================================================
# UPGRADE
# =========================================================

def upgrade() -> None:

    # =====================================================
    # 1. ADD MENU ID AS NULLABLE FIRST
    # =====================================================

    op.add_column(
        "subscription_meal_schedule",
        sa.Column(
            "menu_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # =====================================================
    # 2. BACKFILL EXISTING ROWS
    #
    # Existing SubscriptionMealSchedule rows already have
    # subscription_id.
    #
    # Use the subscription's existing menu_id as the
    # initial snapshot for old schedule records.
    # =====================================================

    op.execute(
        """
        UPDATE subscription_meal_schedule AS sms
        SET menu_id = s.menu_id
        FROM subscriptions AS s
        WHERE sms.subscription_id = s.id
          AND sms.menu_id IS NULL
        """
    )

    # =====================================================
    # 3. SAFETY CHECK
    #
    # If any old schedule still has no menu_id, don't allow
    # migration to silently create broken data.
    # =====================================================

    connection = op.get_bind()

    remaining = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM subscription_meal_schedule
            WHERE menu_id IS NULL
            """
        )
    ).scalar_one()

    if remaining > 0:
        raise RuntimeError(
            "Migration stopped: existing subscription meal "
            "schedule rows could not be assigned a menu_id."
        )

    # =====================================================
    # 4. FOREIGN KEY
    # =====================================================

    op.create_foreign_key(
        "fk_subscription_meal_schedule_menu_id",
        "subscription_meal_schedule",
        "menus",
        ["menu_id"],
        ["id"],
    )

    # =====================================================
    # 5. INDEX
    # =====================================================

    op.create_index(
        "idx_subscription_schedule_menu",
        "subscription_meal_schedule",
        ["menu_id", "date"],
        unique=False,
    )

    # =====================================================
    # 6. NORMAL INDEX ON MENU ID
    # =====================================================

    op.create_index(
        "ix_subscription_meal_schedule_menu_id",
        "subscription_meal_schedule",
        ["menu_id"],
        unique=False,
    )

    # =====================================================
    # 7. NOW MAKE MENU ID REQUIRED
    # =====================================================

    op.alter_column(
        "subscription_meal_schedule",
        "menu_id",
        existing_type=sa.UUID(),
        nullable=False,
    )


# =========================================================
# DOWNGRADE
# =========================================================

def downgrade() -> None:

    # =====================================================
    # DROP INDEXES
    # =====================================================

    op.drop_index(
        "ix_subscription_meal_schedule_menu_id",
        table_name="subscription_meal_schedule",
    )

    op.drop_index(
        "idx_subscription_schedule_menu",
        table_name="subscription_meal_schedule",
    )

    # =====================================================
    # DROP FOREIGN KEY
    # =====================================================

    op.drop_constraint(
        "fk_subscription_meal_schedule_menu_id",
        "subscription_meal_schedule",
        type_="foreignkey",
    )

    # =====================================================
    # DROP COLUMN
    # =====================================================

    op.drop_column(
        "subscription_meal_schedule",
        "menu_id",
    )
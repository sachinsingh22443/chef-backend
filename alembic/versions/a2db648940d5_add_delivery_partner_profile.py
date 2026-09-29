"""add delivery partner profile

Revision ID: a2db648940d5
Revises: dbf733264b71
Create Date: 2026-09-28 23:14:37.068496
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2db648940d5"
down_revision: Union[str, Sequence[str], None] = "dbf733264b71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create delivery partner profiles table."""

    op.create_table(
        "delivery_partner_profiles",

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

        # Personal information
        sa.Column(
            "date_of_birth",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "address",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "city",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "state",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "pincode",
            sa.String(),
            nullable=True,
        ),

        # Profile
        sa.Column(
            "profile_image",
            sa.String(),
            nullable=True,
        ),

        # Vehicle
        sa.Column(
            "vehicle_type",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "vehicle_number",
            sa.String(),
            nullable=True,
        ),

        # Driving licence
        sa.Column(
            "driving_license_number",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "driving_license_image",
            sa.String(),
            nullable=True,
        ),

        # Identity proof
        sa.Column(
            "id_proof_type",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "id_proof_number",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "id_proof_image",
            sa.String(),
            nullable=True,
        ),

        # Bank details
        sa.Column(
            "account_holder_name",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "account_number",
            sa.String(),
            nullable=True,
        ),

        sa.Column(
            "ifsc_code",
            sa.String(),
            nullable=True,
        ),

        # Delivery availability
        sa.Column(
            "is_online",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        sa.Column(
            "is_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        # Current location
        sa.Column(
            "current_latitude",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "current_longitude",
            sa.Float(),
            nullable=True,
        ),

        # Application status
        sa.Column(
            "application_status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),

        sa.Column(
            "rejection_reason",
            sa.String(),
            nullable=True,
        ),

        # Timestamps
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

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    # Unique user -> delivery partner profile
    op.create_index(
        "ix_delivery_partner_profiles_user_id",
        "delivery_partner_profiles",
        ["user_id"],
        unique=True,
    )

    # Search/filter indexes
    op.create_index(
        "ix_delivery_partner_profiles_application_status",
        "delivery_partner_profiles",
        ["application_status"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_partner_profiles_city",
        "delivery_partner_profiles",
        ["city"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_partner_profiles_pincode",
        "delivery_partner_profiles",
        ["pincode"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_partner_profiles_vehicle_number",
        "delivery_partner_profiles",
        ["vehicle_number"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_partner_profiles_driving_license_number",
        "delivery_partner_profiles",
        ["driving_license_number"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_partner_profiles_id_proof_number",
        "delivery_partner_profiles",
        ["id_proof_number"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_partner_profiles_is_online",
        "delivery_partner_profiles",
        ["is_online"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_partner_profiles_is_available",
        "delivery_partner_profiles",
        ["is_available"],
        unique=False,
    )

    op.create_index(
        "ix_delivery_partner_profiles_created_at",
        "delivery_partner_profiles",
        ["created_at"],
        unique=False,
    )

    # Location index
    op.create_index(
        "idx_delivery_partner_location",
        "delivery_partner_profiles",
        ["current_latitude", "current_longitude"],
        unique=False,
    )

    # Combined status index
    op.create_index(
        "idx_delivery_partner_status",
        "delivery_partner_profiles",
        [
            "application_status",
            "is_online",
            "is_available",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Remove delivery partner profiles table."""

    op.drop_index(
        "idx_delivery_partner_status",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "idx_delivery_partner_location",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_created_at",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_is_available",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_is_online",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_id_proof_number",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_driving_license_number",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_vehicle_number",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_pincode",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_city",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_application_status",
        table_name="delivery_partner_profiles",
    )

    op.drop_index(
        "ix_delivery_partner_profiles_user_id",
        table_name="delivery_partner_profiles",
    )

    op.drop_table("delivery_partner_profiles")
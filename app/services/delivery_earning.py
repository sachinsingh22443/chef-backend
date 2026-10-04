from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import DELIVERY_EARNING_PER_ORDER
from app.models.delivery_earning import DeliveryEarning


def create_delivery_earning(
    db: Session,
    delivery_order,
    order,
    delivery_partner_id,
    batch_id=None,
):
    # Prevent duplicate earning
    existing = (
        db.query(DeliveryEarning)
        .filter(
            DeliveryEarning.delivery_order_id
            == delivery_order.id
        )
        .first()
    )

    if existing:
        return existing

    now = datetime.utcnow()

    earning = DeliveryEarning(
        delivery_partner_id=delivery_partner_id,
        delivery_order_id=delivery_order.id,
        order_id=order.id,
        batch_id=batch_id,
        earning_type="per_order",
        delivery_count=1,
        amount=DELIVERY_EARNING_PER_ORDER,
        status="earned",
        earned_at=now,
        created_at=now,
    )

    db.add(earning)
    db.flush()

    return earning
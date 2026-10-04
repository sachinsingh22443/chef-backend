from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    require_role,
)

from app.models.user import User
from app.models.delivery_earning import DeliveryEarning


router = APIRouter(
    prefix="/delivery/earnings",
    tags=["Delivery Earnings"],
)


# ============================================================
# EARNINGS SUMMARY
# ============================================================

@router.get("/summary")
def get_earnings_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(["delivery_partner"])
    ),
):
    today = datetime.utcnow().date()

    today_start = datetime.combine(
        today,
        datetime.min.time(),
    )

    tomorrow_start = (
        today_start + timedelta(days=1)
    )

    week_start = (
        today_start
        - timedelta(
            days=today_start.weekday()
        )
    )

    today_amount = (
        db.query(
            func.coalesce(
                func.sum(
                    DeliveryEarning.amount
                ),
                0,
            )
        )
        .filter(
            DeliveryEarning.delivery_partner_id
            == current_user.id,

            DeliveryEarning.status
            == "earned",

            DeliveryEarning.earned_at
            >= today_start,

            DeliveryEarning.earned_at
            < tomorrow_start,
        )
        .scalar()
    )

    week_amount = (
        db.query(
            func.coalesce(
                func.sum(
                    DeliveryEarning.amount
                ),
                0,
            )
        )
        .filter(
            DeliveryEarning.delivery_partner_id
            == current_user.id,

            DeliveryEarning.status
            == "earned",

            DeliveryEarning.earned_at
            >= week_start,
        )
        .scalar()
    )

    total_amount = (
        db.query(
            func.coalesce(
                func.sum(
                    DeliveryEarning.amount
                ),
                0,
            )
        )
        .filter(
            DeliveryEarning.delivery_partner_id
            == current_user.id,

            DeliveryEarning.status
            == "earned",
        )
        .scalar()
    )

    total_deliveries = (
        db.query(
            func.count(
                DeliveryEarning.id
            )
        )
        .filter(
            DeliveryEarning.delivery_partner_id
            == current_user.id,

            DeliveryEarning.status
            == "earned",
        )
        .scalar()
    )

    return {
        "success": True,

        "today_earnings": float(
            today_amount or 0
        ),

        "week_earnings": float(
            week_amount or 0
        ),

        "total_earnings": float(
            total_amount or 0
        ),

        "total_deliveries": int(
            total_deliveries or 0
        ),
    }
    
    
@router.get("")
def get_earnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(["delivery_partner"])
    ),
):
    earnings = (
        db.query(DeliveryEarning)
        .filter(
            DeliveryEarning.delivery_partner_id
            == current_user.id
        )
        .order_by(
            DeliveryEarning.earned_at.desc()
        )
        .limit(100)
        .all()
    )

    return {
        "success": True,
        "earnings": [
            {
                "id": str(item.id),

                "delivery_order_id": str(
                    item.delivery_order_id
                ),

                "order_id": str(
                    item.order_id
                ),

                "batch_id": (
                    str(item.batch_id)
                    if item.batch_id
                    else None
                ),

                "earning_type": (
                    item.earning_type
                ),

                "amount": float(
                    item.amount
                ),

                "status": item.status,

                "earned_at": (
                    item.earned_at.isoformat()
                    if item.earned_at
                    else None
                ),
            }
            for item in earnings
        ],
    }
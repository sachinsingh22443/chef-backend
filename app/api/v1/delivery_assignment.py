# ============================================================
# 🚚 DELIVERY ASSIGNMENT API
# ============================================================

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    require_role,
)

from app.models.user import User

from app.services.delivery_assignment import (
    run_delivery_assignment,
)


router = APIRouter(
    prefix="/delivery-assignment",
    tags=["Delivery Assignment"],
)


# ============================================================
# RUN AUTOMATIC ASSIGNMENT
# ============================================================

@router.post("/run")
def run_assignment(
    delivery_date: date | None = Query(
        None,
        description="Delivery date YYYY-MM-DD",
    ),

    meal_type: str | None = Query(
        None,
        description=(
            "breakfast / lunch / dinner / special / mixed"
        ),
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_role(["admin"])
    ),
):
    """
    Admin/system endpoint.

    Assigns READY waiting DeliveryOrders
    to eligible delivery partners.
    """

    if meal_type:

        meal_type = (
            meal_type
            .strip()
            .lower()
        )

        allowed_meal_types = {
            "breakfast",
            "lunch",
            "dinner",
            "special",
            "mixed",
        }

        if meal_type not in allowed_meal_types:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid meal_type. Use "
                    "breakfast, lunch, dinner, "
                    "special or mixed."
                ),
            )

    try:

        result = run_delivery_assignment(
            db=db,
            delivery_date=delivery_date,
            meal_type=meal_type,
        )

        return result

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Delivery assignment failed: "
                f"{str(e)}"
            ),
        )
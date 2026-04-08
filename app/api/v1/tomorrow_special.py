from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.tomorrow_special import TomorrowSpecial
from app.schemas.tomorrow_special import TomorrowSpecialCreate

router = APIRouter(prefix="/tomorrow-special", tags=["Tomorrow Special"])


# ✅ CREATE
@router.post("/")
def create_special(
    data: TomorrowSpecialCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    special = TomorrowSpecial(
        chef_id=user.id,
        dish_name=data.dish_name,
        description=data.description,
        price=data.price,
        max_plates=data.max_plates,
        cutoff_time=data.cutoff_time
    )

    db.add(special)
    db.commit()
    db.refresh(special)

    return {"msg": "Tomorrow special created", "id": special.id}


# ✅ GET (chef ka)
from datetime import datetime, timedelta
from sqlalchemy import func

from datetime import datetime
from fastapi import Depends
from sqlalchemy.orm import Session

@router.get("/")
def get_my_specials(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    specials = db.query(TomorrowSpecial)\
        .filter(TomorrowSpecial.chef_id == user.id)\
        .all()

    now = datetime.now()

    valid_specials = []

    for s in specials:
        try:
            # 🔥 combine date + cutoff_time
            cutoff_datetime = datetime.strptime(
                f"{s.created_at.date()} {s.cutoff_time}",
                "%Y-%m-%d %H:%M"
            )

            # 👇 only show if not expired
            if now <= cutoff_datetime:
                valid_specials.append(s)

        except Exception as e:
            print("Time error:", e)

    return valid_specials
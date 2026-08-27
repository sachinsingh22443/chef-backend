from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.security import verify_token
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    # =====================================================
    # VERIFY ACCESS TOKEN
    # =====================================================

    payload = verify_token(token)

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
        )

    # =====================================================
    # FETCH CURRENT USER
    # =====================================================

    user = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.is_active == True,
        )
        .limit(1)
        .first()
    )

    # =====================================================
    # USER NOT FOUND / INACTIVE
    # =====================================================

    if not user:
        raise HTTPException(
            status_code=403,
            detail="User not found or account is inactive",
        )

    return user


def require_role(roles: list):
    """
    Restrict endpoint access based on user role.
    """

    def checker(
        user=Depends(get_current_user),
    ):
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )

        return user

    return checker
import random
import time
import requests
import uuid
from app.schemas.auth import RefreshTokenSchema
from app.core.security import verify_refresh_token
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from pydantic import BaseModel
from app.api.deps import get_db, get_current_user
from app.models.user import User

from app.services.msg91 import send_otp, verify_otp

from app.schemas.auth import CustomerLoginSchema, CustomerSignupSchema, CustomerForgotPasswordSchema, CustomerResetPasswordSchema, ChangePasswordSchema
from app.core.security import (
    create_access_token,
    create_refresh_token
)

from app.models.refresh_token import RefreshToken

from app.utils.hashing import (
    hash_password,
    verify_password,
    hash_refresh_token
)

from datetime import datetime, timedelta

router = APIRouter()


from pydantic import BaseModel

from pydantic import BaseModel
from fastapi import HTTPException

class SendOtpSchema(BaseModel):
    phone: str


@router.post("/send-otp")
def send(data: SendOtpSchema):

    res = send_otp(data.phone)

    print("MSG91 RESPONSE:", res)

    if res.get("type") == "success":
        return {
            "message": "OTP sent successfully",
            "details": res
        }

    raise HTTPException(
        status_code=400,
        detail=res
    )
# SIGNUP
@router.post("/signupapi")
def signupapi(data: CustomerSignupSchema, db: Session = Depends(get_db)):

    if len(data.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    otp_check = verify_otp(data.phone, data.otp)

    if otp_check.get("type") != "success":
        raise HTTPException(400, "Invalid OTP")

    existing = db.query(User).filter(User.phone == data.phone).first()
    if existing:
        raise HTTPException(400, "User already exists")

    user = User(
        name="Customer",
        email=f"{data.phone}@app.com",
        phone=data.phone,
        password=hash_password(data.password),
        role="customer",
        is_verified=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({
      "sub": str(user.id),
      "role": user.role
    })

    refresh_token = create_refresh_token({
       "sub": str(user.id)
    })

    db_token = RefreshToken(
       user_id=user.id,
       token_hash=hash_refresh_token(refresh_token),
       expires_at=datetime.utcnow() + timedelta(days=365)
       )

    db.add(db_token)
    db.commit()

    return {
       "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id)
        }


# LOGIN



@router.post("/loginapi")
def loginapi(data: CustomerLoginSchema, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.phone == data.phone).first()

    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid password")

    # 🔥 TOKEN CREATE
    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    refresh_token = create_refresh_token({
       "sub": str(user.id)
    })

    db_token = RefreshToken(
       user_id=user.id,
       token_hash=hash_refresh_token(refresh_token),
       expires_at=datetime.utcnow() + timedelta(days=365)
    )

    db.add(db_token)
    db.commit()

    return {
      "access_token": access_token,
       "refresh_token": refresh_token,
       "token_type": "bearer",
       "user_id": str(user.id)
    }
# FORGOT PASSWORD
# FORGOT PASSWORD
@router.post("/customer/forgot-password")
def forgot(data: CustomerForgotPasswordSchema):

    res = send_otp(data.phone)

    if res.get("type") == "success":
        return {
            "message": "OTP sent successfully",
            "details": res
        }

    raise HTTPException(
        status_code=400,
        detail=res
    )

# RESET PASSWORD
@router.post("/customer/reset-password")
def reset(data: CustomerResetPasswordSchema, db: Session = Depends(get_db)):

    otp_check = verify_otp(data.phone, data.otp)

    if otp_check.get("type") != "success":
        raise HTTPException(400, "Invalid OTP")

    user = db.query(User).filter(User.phone == data.phone).first()
    if not user:
        raise HTTPException(404, "User not found")

    # 🔥 NEW: same password check
    if verify_password(data.new_password, user.password):
        raise HTTPException(400, "New password cannot be same as old password")

    user.password = hash_password(data.new_password)
    db.commit()

    return {"message": "Password updated successfully"}


# CHANGE PASSWORD
@router.post("/customer/change-password")
def change(
    data: ChangePasswordSchema,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    if not verify_password(data.current_password, user.password):
        raise HTTPException(400, "Wrong password")

    # 🔥 NEW: same password check
    if verify_password(data.new_password, user.password):
        raise HTTPException(400, "New password cannot be same as old password")

    user.password = hash_password(data.new_password)
    db.commit()

    return {"message": "Password changed successfully"}

@router.get("/verify-token")
def verify_token(current_user=Depends(get_current_user)):
    return {"valid": True}



@router.post("/refresh-token")
def refresh_access_token(
    data: RefreshTokenSchema,
    db: Session = Depends(get_db)
):
    # Verify JWT
    payload = verify_refresh_token(data.refresh_token)

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )

    # Hash token
    token_hash = hash_refresh_token(data.refresh_token)

    # Find in DB
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.is_revoked == False
    ).first()

    if not db_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token not found"
        )

    # Check expiry
    if db_token.expires_at < datetime.utcnow():
        db_token.is_revoked = True
        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Refresh token expired"
        )

    # Get User
    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Revoke old token (Rotation)
    db_token.is_revoked = True

    # Create new tokens
    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    refresh_token = create_refresh_token({
        "sub": str(user.id)
    })

    # Save new refresh token
    new_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.utcnow() + timedelta(days=365)
    )

    db.add(new_token)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# DELETE ACCOUNT
@router.delete("/delete-account")
def delete(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(404, "User not found")

    db.delete(user)
    db.commit()

    return {"message": "Account deleted"}
import random
import time
import requests
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from pydantic import BaseModel
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.utils.hashing import hash_password, verify_password

from app.core.security import create_access_token
from app.services.msg91 import send_otp, verify_otp

from app.schemas.auth import CustomerLoginSchema,CustomerSignupSchema,CustomerForgotPasswordSchema,CustomerResetPasswordSchema,ChangePasswordSchema

router = APIRouter()


from pydantic import BaseModel

from pydantic import BaseModel
from fastapi import HTTPException

class SendOtpSchema(BaseModel):
    phone: str


@router.post("/send-otp")
def send(data: SendOtpSchema):

    # 🔥 IMPORTANT: phone format fix (India)
    phone = data.phone
    if not phone.startswith("91"):
        phone = "91" + phone

    res = send_otp(phone)

    print("MSG91 RESPONSE:", res)  # 🔥 DEBUG

    # 🔥 SUCCESS
    if res.get("type") == "success":
        return {
            "message": "OTP sent successfully",
            "details": res   # 🔥 full response show karo
        }

    # 🔴 FAIL CASE
    raise HTTPException(
        status_code=400,
        detail=res  # 🔥 real error dikhega
    )

# SIGNUP
@router.post("/signup")
def signup(data: CustomerSignupSchema, db: Session = Depends(get_db)):

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

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    return {
        "access_token": token,
        "user_id": str(user.id)
    }


# LOGIN



@router.post("/login")
def login(data: CustomerLoginSchema, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.phone == data.phone).first()

    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid password")

    # 🔥 TOKEN CREATE
    token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id)
    }
# FORGOT PASSWORD
@router.post("/forgot-password")
def forgot(data: CustomerForgotPasswordSchema):
    return send_otp(data.phone)


# RESET PASSWORD
@router.post("/reset-password")
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
@router.post("/change-password")
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
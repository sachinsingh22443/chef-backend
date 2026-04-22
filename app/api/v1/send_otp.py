import random
import time
import requests
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.utils.hashing import hash_password, verify_password

from app.core.security import hash_password, verify_password,create_access_token
from app.services.msg91 import send_otp, verify_otp

from app.schemas.auth import SignupSchema, LoginSchema, ResetPasswordSchema, ChangePasswordSchema

router = APIRouter()


@router.post("/send-otp")
def send(phone: str):
    res = send_otp(phone)
    if res.get("type") == "success":
        return {"message": "OTP sent"}
    raise HTTPException(400, "OTP failed")


# SIGNUP
@router.post("/signup")
def signup(data: SignupSchema, db: Session = Depends(get_db)):

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
def login(data: LoginSchema, db: Session = Depends(get_db)):

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
def forgot(phone: str):
    return send_otp(phone)


# RESET PASSWORD
@router.post("/reset-password")
def reset(data: ResetPasswordSchema, db: Session = Depends(get_db)):

    if len(data.new_password) < 6:
        raise HTTPException(400, "Password too short")

    otp_check = verify_otp(data.phone, data.otp)

    if otp_check.get("type") != "success":
        raise HTTPException(400, "Invalid OTP")

    user = db.query(User).filter(User.phone == data.phone).first()
    if not user:
        raise HTTPException(404, "User not found")

    user.password = hash_password(data.new_password)
    db.commit()

    return {"message": "Password updated"}


# CHANGE PASSWORD
@router.post("/change-password")
def change(
    data: ChangePasswordSchema,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    if not verify_password(data.current_password, user.password):
        raise HTTPException(400, "Wrong password")

    if len(data.new_password) < 6:
        raise HTTPException(400, "Password too short")

    user.password = hash_password(data.new_password)
    db.commit()

    return {"message": "Password changed"}


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
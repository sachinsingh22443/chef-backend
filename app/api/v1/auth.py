from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os, secrets, smtplib

from app.models.user import User, ChefProfile
from app.schemas.auth import LoginSchema, ChangePasswordSchema
from app.api.deps import get_db, get_current_user
from app.utils.hashing import hash_password, verify_password
from app.core.security import create_access_token

import cloudinary.uploader

router = APIRouter()


# =========================
# ✅ SIGNUP (FIXED)
# =========================
@router.post("/signup")
async def signup(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),

    address: str = Form(...),
    fssai_number: str = Form(...),

    account_holder_name: str = Form(...),
    account_number: str = Form(...),
    ifsc_code: str = Form(...),

    bio: str = Form(...),
    location: str = Form(...),
    specialties: str = Form(...),

    profile_image: UploadFile = File(...),
    fssai_document: UploadFile = File(...),

    db: Session = Depends(get_db)
):
    try:
        # ✅ NEW: password validation
        if len(password) < 6:
            raise HTTPException(400, "Password must be at least 6 characters")

        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(400, "Email already registered")

        # ✅ NEW: file validation
        if profile_image.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(400, "Invalid profile image")

        if fssai_document.content_type not in ["image/jpeg", "image/png", "application/pdf"]:
            raise HTTPException(400, "Invalid FSSAI document")

        # upload images
        profile_url = cloudinary.uploader.upload(
            await profile_image.read(),
            folder="chef_profiles"
        )["secure_url"]

        fssai_url = cloudinary.uploader.upload(
            await fssai_document.read(),
            folder="fssai_docs"
        )["secure_url"]

        new_user = User(
            name=name,
            email=email,
            phone=phone,
            password=hash_password(password),
            role="chef",
            is_verified=False,
            application_status="under_review"
        )

        db.add(new_user)
        db.flush()

        chef = ChefProfile(
            user_id=new_user.id,
            address=address,
            fssai_number=fssai_number,
            profile_image=profile_url,
            fssai_document=fssai_url,
            account_holder_name=account_holder_name,
            account_number=account_number,
            ifsc_code=ifsc_code,
            bio=bio,
            location=location,
            specialties=specialties
        )

        db.add(chef)
        db.commit()

        return {"msg": "Signup success"}

    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))

# =========================
# ✅ LOGIN
# =========================
@router.post("/login")
def login(user_data: LoginSchema, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == user_data.email).first()

    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # ✅ NEW: role check
    if user.role != "chef":
        raise HTTPException(status_code=403, detail="Not a chef account")

    # ✅ NEW: approval check
    if user.application_status != "approved":
        raise HTTPException(status_code=403, detail="Your account is under review")

    # ✅ NEW: role in token
    token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "application_status": user.application_status
    }
# =========================
# ✅ UPDATE PROFILE (FIXED)
# =========================
@router.put("/users/update-profile")
async def update_profile(
    name: str = Form(None),
    phone: str = Form(None),

    bio: str = Form(None),
    location: str = Form(None),
    specialties: str = Form(None),

    profile_image: UploadFile = File(None),

    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # =========================
        # ✅ COMMON UPDATE (ALL USERS)
        # =========================
        if name:
            current_user.name = name

        if phone:
            current_user.phone = phone

        chef = current_user.chef_profile

        # =========================
        # 🖼 IMAGE UPLOAD (COMMON)
        # =========================
        if profile_image:
            contents = await profile_image.read()

            result = cloudinary.uploader.upload(
                contents,
                folder="profiles"
            )

            image_url = result["secure_url"]

            if current_user.role == "chef" and chef:
                chef.profile_image = image_url
            else:
                current_user.profile_image = image_url

        # =========================
        # 👨‍🍳 CHEF ONLY DATA
        # =========================
        if current_user.role == "chef" and chef:
            if bio:
                chef.bio = bio

            if location:
                chef.location = location

            if specialties:
                chef.specialties = specialties

        db.commit()

        return {
            "msg": "Profile updated successfully"
        }

    except Exception as e:
        db.rollback()
        print("❌ PROFILE ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))



# =========================
# ✅ CHANGE PASSWORD
# =========================
@router.put("/change-password")
def change_password(
    data: ChangePasswordSchema,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    if not verify_password(data.current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password incorrect")

    if len(data.new_password) < 6:
        raise HTTPException(400, "Password too short")

    user.password = hash_password(data.new_password)
    db.commit()

    return {"msg": "Password updated"}


import os
import secrets
import smtplib

from datetime import datetime, timedelta
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.user import User
from app.api.deps import get_db
from app.utils.hashing import hash_password


# 🔥 TEMP STORAGE (production में DB use करना)
reset_tokens = {}

# =========================
# ✅ SCHEMAS
# =========================

class ForgotPasswordSchema(BaseModel):
    email: str


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str


# =========================
# ✅ EMAIL FUNCTION
# =========================

def send_reset_email(to_email: str, reset_link: str):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")

    if not sender_email or not sender_password:
        raise HTTPException(status_code=500, detail="Email config missing")

    subject = "Reset Your Password"
    body = f"""
Hello,

Click the link below to reset your password:

{reset_link}

This link will expire in 15 minutes.

If you did not request this, please ignore this email.
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except Exception as e:
        print("EMAIL ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# 🔐 FORGOT PASSWORD
# =========================

from fastapi import BackgroundTasks

@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = secrets.token_urlsafe(32)

    reset_tokens[token] = {
        "user_id": user.id,
        "expires": datetime.utcnow() + timedelta(minutes=15)
    }

    # ✅ NEW: env based URL
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    reset_link = f"{FRONTEND_URL}/auth/reset-password/{token}"

    # ✅ NEW: background email
    background_tasks.add_task(send_reset_email, user.email, reset_link)

    return {"msg": "Reset link sent to your email"}


# =========================
# 🔑 RESET PASSWORD
# =========================

@router.post("/reset-password")
def reset_password(data: ResetPasswordSchema, db: Session = Depends(get_db)):

    token_data = reset_tokens.get(data.token)

    if not token_data:
        raise HTTPException(status_code=400, detail="Invalid token")

    if token_data["expires"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expired")

    user = db.query(User).filter(User.id == token_data["user_id"]).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 🔐 HASH PASSWORD
    user.password = hash_password(data.new_password)

    db.commit()

    # 🔥 DELETE TOKEN
    del reset_tokens[data.token]

    return {"msg": "Password reset successful"}








@router.delete("/delete-account")
def delete_account(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    db.delete(user)
    db.commit()

    return {"msg": "Account deleted"}
    
# get nearby chefs

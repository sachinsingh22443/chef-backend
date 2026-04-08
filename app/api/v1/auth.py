from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from app.schemas.auth import LoginSchema
from app.models.user import User
from app.models.user import ChefProfile
from app.api.deps import get_db
from app.utils.hashing import hash_password,verify_password
from app.core.security import create_access_token
import os
from app.schemas.auth import ChangePasswordSchema

from app.api.deps import get_db, get_current_user
from app.utils.hashing import hash_password, verify_password  



router = APIRouter()







import uuid

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(400, "Email already registered")

    try:
        # 🔥 UNIQUE FILE NAMES
        profile_filename = f"{uuid.uuid4()}_{profile_image.filename}"
        profile_path = f"uploads/{profile_filename}"

        with open(profile_path, "wb") as f:
            f.write(await profile_image.read())

        fssai_filename = f"{uuid.uuid4()}_{fssai_document.filename}"
        fssai_path = f"uploads/{fssai_filename}"

        with open(fssai_path, "wb") as f:
            f.write(await fssai_document.read())

        # 🔹 CREATE USER
        new_user = User(
            name=name,
            email=email,
            phone=phone,
            password=hash_password(password),
            is_verified=False,
            application_status="under_review"
        )
        db.add(new_user)
        db.flush()  # ID mil jayega

        # 🔹 CREATE CHEF PROFILE
        chef = ChefProfile(
            user_id=new_user.id,
            address=address,
            fssai_number=fssai_number,
            profile_image=profile_path,   # ✅ FIXED
            fssai_document=fssai_path,    # ✅ FIXED
            account_holder_name=account_holder_name,
            account_number=account_number,
            ifsc_code=ifsc_code,
            bio=bio,
            location=location,
            specialties=specialties
        )

        db.add(chef)

        db.commit()
        db.refresh(new_user)
        db.refresh(chef)

    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))

    return {"msg": "Signup success"}


@router.post("/login")
def login(user_data: LoginSchema, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == user_data.email).first()

    # ✅ Avoid user enumeration
    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # ✅ OTP check
    # if not user.is_verified:
    #     raise HTTPException(status_code=401, detail="Please verify OTP first")

    # ✅ Account active check
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer",
        "application_status": user.application_status
    }
    
    

# from fastapi import APIRouter, Depends
from app.api.deps import get_current_user


@router.get("/status")
def get_application_status(current_user=Depends(get_current_user)):
    return {
        "status": current_user.application_status,
        "reason": current_user.rejection_reason
    }
    
@router.put("/admin/approve/{user_id}")
def approve_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()

    user.application_status = "approved"
    user.rejection_reason = None

    db.commit()

    return {"msg": "User approved"}

@router.put("/admin/reject/{user_id}")
def reject_user(user_id: str, reason: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()

    user.application_status = "rejected"
    user.rejection_reason = reason

    db.commit()

    return {"msg": "User rejected"}



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
        # 🔹 USER update
        if name:
            current_user.name = name
        if phone:
            current_user.phone = phone

        # 🔹 ChefProfile
        chef = current_user.chef_profile

        if not chef:
            raise HTTPException(404, "Chef profile not found")

        if bio:
            chef.bio = bio
        if location:
            chef.location = location
        if specialties:
            chef.specialties = specialties

        # 🔹 Image update
        if profile_image:
            file_path = os.path.join(UPLOAD_DIR, profile_image.filename)
            with open(file_path, "wb") as f:
                f.write(await profile_image.read())

            chef.profile_image = file_path

        db.commit()
        db.refresh(current_user)
        db.refresh(chef)

        return {"msg": "Profile updated successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(500, str(e))
    
    



# 👈 tumhara file



@router.put("/change-password")
def change_password(
    data: ChangePasswordSchema,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    if not verify_password(data.current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password incorrect")

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

@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordSchema, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = secrets.token_urlsafe(32)

    reset_tokens[token] = {
        "user_id": user.id,
        "expires": datetime.utcnow() + timedelta(minutes=15)
    }

    # ⚠️ FRONTEND PORT CHANGE ACCORDINGLY
    reset_link = f"http://localhost:5173/auth/reset-password/{token}"

    # DEBUG (optional)
    print("RESET LINK:", reset_link)

    send_reset_email(user.email, reset_link)

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
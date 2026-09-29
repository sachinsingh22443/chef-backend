from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Form,
    File,
    UploadFile,
    BackgroundTasks,
)

from sqlalchemy.orm import Session

from datetime import datetime, timedelta

import os
import secrets
import smtplib

from pydantic import BaseModel

from app.models.user import User, ChefProfile
from app.services.msg91 import send_otp, verify_otp
from app.models.delivery_partner import DeliveryPartnerProfile
from app.models.refresh_token import RefreshToken

from app.schemas.auth import (
    ChefLoginSchema,
    ChangePasswordSchema,
    DeliveryPartnerSignupSchema,
)

from app.api.deps import (
    get_db,
    get_current_user,
)

from app.utils.hashing import (
    hash_password,
    verify_password,
)

from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    hash_refresh_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

import cloudinary.uploader

from email.mime.text import MIMEText


router = APIRouter()

class DeliveryPartnerLoginSchema(BaseModel):
    phone: str
    password: str
    
   

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

        existing_user = (
          db.query(User)
          .filter(User.email == email)
          .limit(1)
          .first()
        )
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
# =========================
# ✅ LOGIN
# =========================
# =========================================================
# LOGIN
# =========================================================

# =========================================================
# 🚴 DELIVERY PARTNER SIGNUP
# =========================================================

@router.post("/delivery/signup")
async def delivery_partner_signup(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),

    otp: str = Form(...),

    date_of_birth: str = Form(None),

    address: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    pincode: str = Form(...),

    vehicle_type: str = Form(...),
    vehicle_number: str = Form(...),

    driving_license_number: str = Form(...),
    driving_license_image: UploadFile = File(...),

    id_proof_type: str = Form(...),
    id_proof_number: str = Form(...),
    id_proof_image: UploadFile = File(...),

    account_holder_name: str = Form(...),
    account_number: str = Form(...),
    ifsc_code: str = Form(...),

    db: Session = Depends(get_db),
):
    try:

        # =====================================================
        # 1. BASIC VALIDATION
        # =====================================================

        name = name.strip()
        email = email.strip().lower()
        phone = phone.strip()
        vehicle_type = vehicle_type.strip()
        vehicle_number = vehicle_number.strip().upper()
        driving_license_number = driving_license_number.strip().upper()
        id_proof_type = id_proof_type.strip()
        id_proof_number = id_proof_number.strip()
        ifsc_code = ifsc_code.strip().upper()

        if len(password) < 6:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 6 characters"
            )

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Name is required"
            )

        if not phone:
            raise HTTPException(
                status_code=400,
                detail="Phone number is required"
            )

        # =====================================================
        # 2. OTP VERIFY
        # =====================================================

        otp_check = verify_otp(
            phone,
            otp
        )

        if otp_check.get("type") != "success":
            raise HTTPException(
                status_code=400,
                detail="Invalid OTP"
            )

        # =====================================================
        # 3. CHECK EXISTING PHONE
        # =====================================================

        existing_phone = (
            db.query(User)
            .filter(User.phone == phone)
            .limit(1)
            .first()
        )

        if existing_phone:
            raise HTTPException(
                status_code=400,
                detail="Phone number already registered"
            )

        # =====================================================
        # 4. CHECK EXISTING EMAIL
        # =====================================================

        existing_email = (
            db.query(User)
            .filter(User.email == email)
            .limit(1)
            .first()
        )

        if existing_email:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        # =====================================================
        # 5. CHECK VEHICLE NUMBER
        # =====================================================

        existing_vehicle = (
            db.query(DeliveryPartnerProfile)
            .filter(
                DeliveryPartnerProfile.vehicle_number
                == vehicle_number
            )
            .limit(1)
            .first()
        )

        if existing_vehicle:
            raise HTTPException(
                status_code=400,
                detail="Vehicle number already registered"
            )

        # =====================================================
        # 6. CHECK DRIVING LICENCE
        # =====================================================

        existing_license = (
            db.query(DeliveryPartnerProfile)
            .filter(
                DeliveryPartnerProfile.driving_license_number
                == driving_license_number
            )
            .limit(1)
            .first()
        )

        if existing_license:
            raise HTTPException(
                status_code=400,
                detail="Driving licence already registered"
            )

        # =====================================================
        # 7. FILE VALIDATION
        # =====================================================

        allowed_images = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
        ]

        if (
            driving_license_image.content_type
            not in allowed_images
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid driving licence image"
            )

        if (
            id_proof_image.content_type
            not in allowed_images
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid ID proof image"
            )

        # =====================================================
        # 8. UPLOAD DRIVING LICENCE
        # =====================================================

        driving_license_url = cloudinary.uploader.upload(
            await driving_license_image.read(),
            folder="delivery_partner/driving_licenses",
            resource_type="image",
        )["secure_url"]

        # =====================================================
        # 9. UPLOAD ID PROOF
        # =====================================================

        id_proof_url = cloudinary.uploader.upload(
            await id_proof_image.read(),
            folder="delivery_partner/id_proofs",
            resource_type="image",
        )["secure_url"]

        # =====================================================
        # 10. CREATE USER
        # =====================================================

        new_user = User(
            name=name,
            email=email,
            phone=phone,
            password=hash_password(password),

            role="delivery_partner",

            # OTP verified
            is_verified=True,

            # Admin approval ke baad active hoga
            is_active=False,

            # Application pending
            application_status="pending",
        )

        db.add(new_user)

        # user.id generate karne ke liye
        db.flush()

        # =====================================================
        # 11. CREATE DELIVERY PARTNER PROFILE
        # =====================================================

        delivery_profile = DeliveryPartnerProfile(
            user_id=new_user.id,

            date_of_birth=date_of_birth,

            address=address,
            city=city,
            state=state,
            pincode=pincode,

            vehicle_type=vehicle_type,
            vehicle_number=vehicle_number,

            driving_license_number=driving_license_number,
            driving_license_image=driving_license_url,

            id_proof_type=id_proof_type,
            id_proof_number=id_proof_number,
            id_proof_image=id_proof_url,

            account_holder_name=account_holder_name,
            account_number=account_number,
            ifsc_code=ifsc_code,

            # Signup ke baad
            is_online=False,
            is_available=False,

            # Location baad me app se milegi
            current_latitude=None,
            current_longitude=None,

            application_status="pending",
            rejection_reason=None,
        )

        db.add(delivery_profile)

        # =====================================================
        # 12. COMMIT
        # =====================================================

        db.commit()

        db.refresh(new_user)
        db.refresh(delivery_profile)

        # =====================================================
        # 13. RESPONSE
        # =====================================================

        return {
            "message": "Delivery partner application submitted successfully",

            "user_id": str(new_user.id),

            "role": new_user.role,

            "application_status":
                new_user.application_status,

            "is_active":
                new_user.is_active,

            "profile_id":
                str(delivery_profile.id),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        print(
            "DELIVERY PARTNER SIGNUP ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to create delivery partner application"
        )

@router.post("/login")
def login(
    user_data: ChefLoginSchema,
    db: Session = Depends(get_db)
):

    # =====================================================
    # FIND USER
    # =====================================================

    user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .limit(1)
        .first()
    )

    # =====================================================
    # CHECK CREDENTIALS
    # =====================================================

    if not user or not verify_password(
        user_data.password,
        user.password
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid credentials"
        )

    # =====================================================
    # ACCOUNT CHECK
    # =====================================================

    if not user.is_active:

        raise HTTPException(
            status_code=403,
            detail="Account is disabled"
        )

    # =====================================================
    # ROLE CHECK
    # =====================================================

    if user.role != "chef":

        raise HTTPException(
            status_code=403,
            detail="Not a chef account"
        )

    # =====================================================
    # APPROVAL CHECK
    # =====================================================

    if user.application_status != "approved":

        raise HTTPException(
            status_code=403,
            detail="Your account is under review"
        )

    # =====================================================
    # CREATE ACCESS TOKEN
    # =====================================================

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    # =====================================================
    # CREATE REFRESH TOKEN
    # =====================================================

    refresh_token = create_refresh_token({
        "sub": str(user.id),
        "role": user.role
    })

    # =====================================================
    # SAVE REFRESH TOKEN IN DATABASE
    # =====================================================

    refresh_token_record = RefreshToken(
        user_id=user.id,

        token_hash=hash_refresh_token(
            refresh_token
        ),

        expires_at=(
            datetime.utcnow()
            + timedelta(
                days=REFRESH_TOKEN_EXPIRE_DAYS
            )
        ),

        is_revoked=False,
    )

    db.add(refresh_token_record)

    db.commit()

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "application_status": user.application_status
    }
    
# =========================
# 🔄 REFRESH TOKEN SCHEMA
# =========================



# # =========================
# # 🔄 REFRESH ACCESS TOKEN
# # =========================
# # =========================
# # 🔄 CUSTOMER REFRESH TOKEN
# # =========================
# =========================================================
# REFRESH TOKEN SCHEMA
# =========================================================


# =========================================================
# 🚚 DELIVERY PARTNER LOGIN
# =========================================================

@router.post("/delivery/login")
def delivery_partner_login(
    data: DeliveryPartnerLoginSchema,
    db: Session = Depends(get_db)
):

    # =====================================================
    # 1️⃣ CLEAN PHONE
    # =====================================================

    phone = data.phone.strip()

    # =====================================================
    # 2️⃣ FIND USER
    # =====================================================

    user = (
        db.query(User)
        .filter(
            User.phone == phone,
            User.role == "delivery_partner"
        )
        .limit(1)
        .first()
    )

    # =====================================================
    # 3️⃣ CHECK USER + PASSWORD
    # =====================================================

    if not user or not verify_password(
        data.password,
        user.password
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number or password"
        )

    # =====================================================
    # 4️⃣ APPROVAL CHECK
    # =====================================================

    if user.application_status == "pending":

        raise HTTPException(
            status_code=403,
            detail="Your delivery partner application is still under review"
        )

    # =====================================================
    # 5️⃣ REJECTED CHECK
    # =====================================================

    if user.application_status == "rejected":

        profile = (
            db.query(DeliveryPartnerProfile)
            .filter(
                DeliveryPartnerProfile.user_id == user.id
            )
            .first()
        )

        rejection_reason = (
            profile.rejection_reason
            if profile
            else user.rejection_reason
        )

        raise HTTPException(
            status_code=403,
            detail=(
                rejection_reason
                or "Your delivery partner application was rejected"
            )
        )

    # =====================================================
    # 6️⃣ APPROVED CHECK
    # =====================================================

    if user.application_status != "approved":

        raise HTTPException(
            status_code=403,
            detail="Your delivery partner application is not approved"
        )

    # =====================================================
    # 7️⃣ ACTIVE CHECK
    # =====================================================

    if not user.is_active:

        raise HTTPException(
            status_code=403,
            detail="Your delivery partner account is disabled"
        )

    # =====================================================
    # 8️⃣ GET PROFILE
    # =====================================================

    profile = (
        db.query(DeliveryPartnerProfile)
        .filter(
            DeliveryPartnerProfile.user_id == user.id
        )
        .first()
    )

    if not profile:

        raise HTTPException(
            status_code=404,
            detail="Delivery partner profile not found"
        )

    # =====================================================
    # 9️⃣ CREATE ACCESS TOKEN
    # =====================================================

    access_token = create_access_token({
        "sub": str(user.id),
        "role": "delivery_partner"
    })

    # =====================================================
    # 🔟 CREATE REFRESH TOKEN
    # =====================================================

    refresh_token = create_refresh_token({
        "sub": str(user.id),
        "role": "delivery_partner"
    })

    # =====================================================
    # 1️⃣1️⃣ SAVE REFRESH TOKEN
    # =====================================================

    refresh_token_record = RefreshToken(
        user_id=user.id,

        token_hash=hash_refresh_token(
            refresh_token
        ),

        expires_at=(
            datetime.utcnow()
            + timedelta(
                days=REFRESH_TOKEN_EXPIRE_DAYS
            )
        ),

        is_revoked=False,
    )

    db.add(refresh_token_record)

    db.commit()

    # =====================================================
    # 1️⃣2️⃣ RESPONSE
    # =====================================================

    return {
        "message": "Delivery partner login successful",

        "access_token": access_token,

        "refresh_token": refresh_token,

        "token_type": "bearer",

        "user_id": str(user.id),

        "role": "delivery_partner",

        "application_status": user.application_status,

        "is_active": user.is_active,

        "is_online": profile.is_online,

        "is_available": profile.is_available,

        "profile_id": str(profile.id)
    }

class RefreshTokenRequest(BaseModel):
    refresh_token: str


# =========================================================
# REFRESH ACCESS TOKEN
# =========================================================

@router.post("/refresh")
def refresh_access_token(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):

    # =====================================================
    # 1. VERIFY JWT REFRESH TOKEN
    # =====================================================

    payload = verify_refresh_token(
        data.refresh_token
    )

    user_id = payload.get("sub")
    jti = payload.get("jti")

    if not user_id or not jti:

        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )

    # =====================================================
    # 2. FIND USER
    # =====================================================

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    # =====================================================
    # 3. ACCOUNT CHECK
    # =====================================================

    if not user.is_active:

        raise HTTPException(
            status_code=403,
            detail="Account is disabled"
        )

    # =====================================================
    # 4. HASH TOKEN
    # =====================================================

    incoming_token_hash = hash_refresh_token(
        data.refresh_token
    )

    # =====================================================
    # 5. FIND TOKEN IN DATABASE
    # =====================================================

    stored_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == incoming_token_hash,
            RefreshToken.user_id == user.id,
        )
        .first()
    )

    # =====================================================
    # TOKEN NOT FOUND
    # =====================================================

    if not stored_token:

        raise HTTPException(
            status_code=401,
            detail="Refresh token not found"
        )

    # =====================================================
    # 6. CHECK REVOCATION
    # =====================================================

    if stored_token.is_revoked:

        raise HTTPException(
            status_code=401,
            detail="Refresh token revoked"
        )

    # =====================================================
    # 7. CHECK DATABASE EXPIRY
    # =====================================================

    if stored_token.expires_at < datetime.utcnow():

        stored_token.is_revoked = True

        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Refresh token expired"
        )

    # =====================================================
    # 8. REVOKE OLD REFRESH TOKEN
    # =====================================================

    stored_token.is_revoked = True

    # =====================================================
    # 9. CREATE NEW ACCESS TOKEN
    # =====================================================

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    # =====================================================
    # 10. CREATE NEW REFRESH TOKEN
    # =====================================================

    new_refresh_token = create_refresh_token({
        "sub": str(user.id),
        "role": user.role
    })

    # =====================================================
    # 11. SAVE NEW REFRESH TOKEN
    # =====================================================

    new_token = RefreshToken(
        user_id=user.id,

        token_hash=hash_refresh_token(
            new_refresh_token
        ),

        expires_at=(
            datetime.utcnow()
            + timedelta(
                days=REFRESH_TOKEN_EXPIRE_DAYS
            )
        ),

        is_revoked=False,
    )

    db.add(new_token)

    db.commit()

    # =====================================================
    # 12. RETURN NEW TOKENS
    # =====================================================

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id)
    }
    # =========================
    # 💾 SAVE NEW REFRESH TOKEN
    # =========================
#     from app.models.refresh_token import RefreshToken
#     from app.core.security import hash_refresh_token

#     new_token = RefreshToken(
#         user_id=user.id,
#         token_hash=hash_refresh_token(
#             new_refresh_token
#         ),
#         expires_at=(
#             datetime.utcnow()
#             + timedelta(days=365)
#         )
#     )

#     db.add(new_token)
#     db.commit()

#     return {
#         "access_token": access_token,
#         "refresh_token": new_refresh_token,
#         "token_type": "bearer",
#         "user_id": str(user.id)
#     }
# # =========================
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




# 🔥 TEMP STORAGE (production में DB use करना)
reset_tokens = {}

# =========================
# ✅ SCHEMAS
# =========================
from pydantic import BaseModel
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
    user = (
      db.query(User)
      .filter(User.email == data.email)
      .limit(1)
      .first()
    )

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

    user = (
      db.query(User)
      .filter(User.id == token_data["user_id"])
      .limit(1)
      .first()
    )

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

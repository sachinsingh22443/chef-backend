
from app.schemas.auth import RefreshTokenSchema
from app.core.security import verify_refresh_token
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.api.deps import get_db, get_current_user
from app.models.user import User
import secrets
import string

from app.models.referral import Referral

from app.services.msg91 import send_otp, verify_otp

from app.schemas.auth import CustomerLoginSchema, CustomerSignupSchema, CustomerForgotPasswordSchema, CustomerResetPasswordSchema, ChangePasswordSchema
from app.core.security import (
    create_access_token,
    create_refresh_token
)


from app.utils.hashing import (
    hash_password,
    verify_password,
    hash_refresh_token
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token
)

from app.models.refresh_token import RefreshToken



from datetime import datetime, timedelta

router = APIRouter()




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
# =========================================================
# 📱 CUSTOMER SIGNUP
# =========================================================

@router.post("/signupapi")
def signupapi(
    data: CustomerSignupSchema,
    db: Session = Depends(get_db)
):

    # =====================================================
    # 🔐 PASSWORD VALIDATION
    # =====================================================

    if len(data.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters"
        )

    # =====================================================
    # 📲 OTP VERIFICATION
    # =====================================================

    otp_check = verify_otp(
        data.phone,
        data.otp
    )

    if otp_check.get("type") != "success":
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP"
        )

    # =====================================================
    # 👤 CHECK EXISTING USER
    # =====================================================

    existing = (
        db.query(User)
        .filter(User.phone == data.phone)
        .limit(1)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    # =====================================================
    # 🎁 CLEAN REFERRAL CODE
    # =====================================================

    referral_code = None

    if data.referral_code:

        referral_code = data.referral_code.strip().upper()

        if referral_code == "":
            referral_code = None

    # =====================================================
    # 🎁 FIND REFERRER
    # =====================================================

    referrer = None

    if referral_code:

        referrer = (
            db.query(User)
            .filter(
                User.referral_code == referral_code,
                User.role == "customer",
                User.is_active == True
            )
            .first()
        )

        # =================================================
        # ❌ INVALID REFERRAL CODE
        # =================================================

        if not referrer:
            raise HTTPException(
                status_code=400,
                detail="Invalid referral code"
            )

        # =================================================
        # 🚫 SELF REFERRAL
        # =================================================

        if referrer.phone == data.phone:
            raise HTTPException(
                status_code=400,
                detail="You cannot use your own referral code"
            )

    # =====================================================
    # 🔑 GENERATE UNIQUE REFERRAL CODE
    # FOR NEW CUSTOMER
    # =====================================================

    def generate_referral_code():

        characters = string.ascii_uppercase + string.digits

        for _ in range(20):

            code = (
                "EU"
                + "".join(
                    secrets.choice(characters)
                    for _ in range(8)
                )
            )

            exists = (
                db.query(User.id)
                .filter(
                    User.referral_code == code
                )
                .first()
            )

            if not exists:
                return code

        raise HTTPException(
            status_code=500,
            detail="Unable to generate referral code"
        )

    new_referral_code = generate_referral_code()

    # =====================================================
    # 👤 CREATE CUSTOMER
    # =====================================================

    user = User(
        name="Customer",
        email=f"{data.phone}@app.com",
        phone=data.phone,
        password=hash_password(data.password),
        role="customer",
        is_verified=True,
        is_active=True,

        # New customer's own referral code
        referral_code=new_referral_code,

        # Who referred this customer
        referred_by=(
            referrer.id
            if referrer
            else None
        )
    )

    try:

        # =================================================
        # 💾 ADD USER
        # =================================================

        db.add(user)

        # Generate user.id before Referral creation
        db.flush()

        # =================================================
        # 🎁 CREATE REFERRAL RECORD
        # =================================================

        if referrer:

            referral = Referral(
                referrer_id=referrer.id,
                referred_user_id=user.id,

                # Referral code actually used
                referral_code=referral_code,

                # Signup does NOT give reward
                status="PENDING",

                reward_amount=0.0,
                reward_type=None,

                order_id=None,
                subscription_id=None,

                rewarded_at=None,
                cancelled_at=None,
                cancellation_reason=None
            )

            db.add(referral)

            # Execute DB constraints now
            db.flush()

        # =================================================
        # 💾 COMMIT USER + REFERRAL TOGETHER
        # =================================================

        db.commit()

        db.refresh(user)

    except Exception as e:

        db.rollback()

        print(
            "SIGNUP REFERRAL ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to create account. Please try again."
        )

    # =====================================================
    # 🔐 ACCESS TOKEN
    # =====================================================

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    # =====================================================
    # 🔄 REFRESH TOKEN
    # =====================================================

    refresh_token = create_refresh_token({
        "sub": str(user.id)
    })

    # =====================================================
    # 💾 SAVE REFRESH TOKEN
    # =====================================================

    db_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(
            refresh_token
        ),
        expires_at=(
            datetime.utcnow()
            + timedelta(days=365)
        )
    )

    db.add(db_token)
    db.commit()

    # =====================================================
    # ✅ RESPONSE
    # =====================================================

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id),

        # New user's referral code
        "referral_code": user.referral_code,

        # True if another customer referred this user
        "referral_applied": bool(referrer)
    }

# LOGIN



@router.post("/loginapi")
def loginapi(data: CustomerLoginSchema, db: Session = Depends(get_db)):

    user = (
      db.query(User)
      .filter(User.phone == data.phone)
      .limit(1)
      .first()
    )

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

    user = (
     db.query(User)
     .filter(User.phone == data.phone)
     .limit(1)
     .first()
    )
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


# =========================
# 🔄 CUSTOMER REFRESH TOKEN
# =========================

@router.post("/customer-refresh")
def customer_refresh_access_token(
    data: RefreshTokenSchema,
    db: Session = Depends(get_db)
):
    # =========================
    # 🔐 VERIFY REFRESH JWT
    # =========================
    payload = verify_refresh_token(data.refresh_token)

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )

    # =========================
    # 🔐 HASH REFRESH TOKEN
    # =========================
    token_hash = hash_refresh_token(
        data.refresh_token
    )

    # =========================
    # 🔎 FIND TOKEN IN DB
    # =========================
    db_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False
        )
        .first()
    )

    if not db_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token not found"
        )

    # =========================
    # ⏰ CHECK EXPIRY
    # =========================
    if db_token.expires_at < datetime.utcnow():
        db_token.is_revoked = True
        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Refresh token expired"
        )

    # =========================
    # 👤 FIND CUSTOMER
    # =========================
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # =========================
    # 🚫 ACCOUNT CHECK
    # =========================
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled"
        )

    # =========================
    # 🔄 REVOKE OLD TOKEN
    # =========================
    db_token.is_revoked = True

    # =========================
    # 🔐 CREATE NEW ACCESS TOKEN
    # =========================
    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    # =========================
    # 🔄 CREATE NEW REFRESH TOKEN
    # =========================
    new_refresh_token = create_refresh_token({
        "sub": str(user.id)
    })

    # =========================
    # 💾 SAVE NEW REFRESH TOKEN
    # =========================
    new_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(
            new_refresh_token
        ),
        expires_at=(
            datetime.utcnow()
            + timedelta(days=365)
        )
    )

    db.add(new_token)
    db.commit()

    # =========================
    # 📦 RESPONSE
    # =========================
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id)
    }
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

    user.is_active = False
    db.commit()

    return {"message": "Account deleted"}
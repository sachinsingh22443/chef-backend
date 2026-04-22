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
from app.api.deps import get_db

# router = APIRouter()

# API_KEY = "qthlS9xDumOzjEr1Z0kcGMLXVeyiYdWU8FbvRH3fsPgCAn7N6KqZafxpQMCRVUej9nEb5tG4W1gFo2zv"


# from datetime import datetime, timedelta
# from jose import jwt

# SECRET_KEY = "supersecretkey"   # 🔥 change in production
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 60


# def create_access_token(data: dict):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# otp_store = {}

# # ✅ Pydantic Models
# class SendOTPRequest(BaseModel):
#     phone: str

# class SignupRequest(BaseModel):
#     phone: str
#     otp: str
#     password: str

# class LoginRequest(BaseModel):
#     phone: str
#     password: str


# # 📲 SEND OTP
# @router.post("/send-otp")
# def send_otp(data: SendOTPRequest):
#     phone = data.phone

#     otp = random.randint(100000, 999999)

#     url = "https://www.fast2sms.com/dev/bulkV2"

#     params = {
#         "authorization": API_KEY,
#         "route": "q",   # ✅ FIX: otp → q
#         "message": f"Your OTP is {otp}",  # ✅ FIX
#         "numbers": phone
#     }

#     response = requests.get(url, params=params)

#     print("SMS RESPONSE:", response.text)
#     print("OTP:", otp)  # 🔥 testing ke liye

#     otp_store[phone] = {
#         "otp": str(otp),
#         "expires": time.time() + 300
#     }

#     return {"message": "OTP sent successfully"}

# # 🔐 VERIFY OTP + SIGNUP
# @router.post("/verify-otp-signup")
# def verify_otp_signup(data: SignupRequest, db: Session = Depends(get_db)):

#     phone = data.phone
#     otp = data.otp
#     password = data.password

#     print("PHONE:", phone)
#     print("OTP:", otp)

#     record = otp_store.get(phone)

#     if not record:
#         raise HTTPException(status_code=400, detail="OTP not found")

#     if time.time() > record["expires"]:
#         raise HTTPException(status_code=400, detail="OTP expired")

#     if str(record["otp"]) != str(otp):
#         raise HTTPException(status_code=400, detail="Invalid OTP")

#     existing_user = db.query(User).filter(User.phone == phone).first()
#     if existing_user:
#         raise HTTPException(status_code=400, detail="User already exists")

#     hashed_password = hash_password(password)

#     new_user = User(
#         id=uuid.uuid4(),
#         name="User",
#         email=f"{phone}@temp.com",
#         phone=phone,
#         password=hashed_password,
#         is_verified=True
#     )

#     db.add(new_user)
#     db.commit()
#     db.refresh(new_user)

#     del otp_store[phone]

#     return {"message": "User created successfully"}


# # 🔑 LOGIN
# @router.post("/loginapi")
# def login_api(data: LoginRequest, db: Session = Depends(get_db)):

#     phone = data.phone.strip()
#     password = data.password.strip()

#     # 🔥 input validation
#     if not phone or not password:
#         raise HTTPException(status_code=400, detail="Phone and password required")

#     # 🔥 find user
#     user = db.query(User).filter(User.phone == phone).first()

#     if not user:
#         raise HTTPException(status_code=400, detail="User not found")

#     # 🔥 ACCOUNT DELETED CHECK
#     if hasattr(user, "is_deleted") and user.is_deleted:
#         raise HTTPException(status_code=403, detail="Account deleted")

#     # 🔥 ACCOUNT BLOCKED CHECK (future)
#     if hasattr(user, "is_blocked") and user.is_blocked:
#         return {
#             "blocked": True,
#             "reason": getattr(user, "block_reason", "Violation of policy")
#         }

#     # 🔐 password verify
#     if not verify_password(password, user.password):
#         raise HTTPException(status_code=400, detail="Invalid password")

#     # 🔥 create JWT token
#     access_token = create_access_token(
#         data={"sub": str(user.id)}
#     )

#     return {
#         "access_token": access_token,
#         "token_type": "bearer",
#         "user_id": str(user.id),
#         "phone": user.phone,
#         "name": user.name,
#         "role": user.role if hasattr(user, "role") else "customer"
#     }
# class ForgotPasswordRequest(BaseModel):
#     phone: str


# @router.post("/forgot-password/send-otp")
# def forgot_send_otp(data: ForgotPasswordRequest):
#     phone = data.phone

#     otp = random.randint(100000, 999999)

#     otp_store[phone] = {
#         "otp": str(otp),
#         "expires": time.time() + 300
#     }

#     print("RESET OTP:", otp)

#     return {"message": "OTP sent for password reset"}


# class VerifyOTPRequest(BaseModel):
#     phone: str
#     otp: str


# @router.post("/forgot-password/verify-otp")
# def verify_otp(data: VerifyOTPRequest):
#     record = otp_store.get(data.phone)

#     if not record:
#         raise HTTPException(400, "OTP not found")

#     if time.time() > record["expires"]:
#         raise HTTPException(400, "OTP expired")

#     if record["otp"] != data.otp:
#         raise HTTPException(400, "Invalid OTP")

#     return {"message": "OTP verified"}


# class ResetPasswordRequest(BaseModel):
#     phone: str
#     new_password: str


# @router.post("/forgot-password/reset")
# def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):

#     user = db.query(User).filter(User.phone == data.phone).first()

#     if not user:
#         raise HTTPException(404, "User not found")

#     user.password = hash_password(data.new_password)

#     db.commit()

#     return {"message": "Password updated successfully"}


# class ChangePasswordRequest(BaseModel):
#     current_password: str
#     new_password: str


# @router.post("/change-password")
# def change_password(
#     data: ChangePasswordRequest,
#     db: Session = Depends(get_db),
#     user=Depends(get_current_user)
# ):
#     if not verify_password(data.current_password, user.password):
#         raise HTTPException(400, "Wrong current password")

#     user.password = hash_password(data.new_password)
#     db.commit()

#     return {"message": "Password changed"}


# from fastapi import Body

# class DeleteAccountRequest(BaseModel):
#     password: str | None = None   # optional (security ke liye)


# @router.delete("/delete-account")
# def delete_account(
#     data: DeleteAccountRequest = Body(default=None),
#     db: Session = Depends(get_db),
#     user: User = Depends(get_current_user)
# ):
#     # 🔥 user check
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     # 🔐 OPTIONAL SECURITY (recommended)
#     if data and data.password:
#         if not verify_password(data.password, user.password):
#             raise HTTPException(status_code=400, detail="Wrong password")

#     try:
#         # 🔥 HARD DELETE (simple)
#         db.delete(user)
#         db.commit()

#         return {"message": "Account deleted successfully"}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.security import hash_password, verify_password, create_token
from app.services.msg91 import send_otp, verify_otp

from app.schemas.auth import SignupSchema, LoginSchema, ResetPasswordSchema, ChangePasswordSchema

router = APIRouter()

# SEND OTP
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

    token = create_token({
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
        raise HTTPException(400, "User not found")

    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    if not verify_password(data.password, user.password):
        raise HTTPException(400, "Wrong password")

    token = create_token({
        "sub": str(user.id),
        "role": user.role
    })

    return {
        "access_token": token,
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
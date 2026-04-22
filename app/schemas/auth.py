from pydantic import BaseModel, Field


# =========================
# 📱 CUSTOMER SIGNUP
# =========================
class CustomerSignupSchema(BaseModel):
    phone: str
    password: str = Field(min_length=6)   # 🔥 fixed
    otp: str


# =========================
# 🔐 CUSTOMER LOGIN
# =========================
class CustomerLoginSchema(BaseModel):
    phone: str
    password: str = Field(min_length=6)


# =========================
# 🔐 FORGOT PASSWORD (OTP)
# =========================
class CustomerForgotPasswordSchema(BaseModel):
    phone: str


# =========================
# 🔑 RESET PASSWORD (OTP)
# =========================
class CustomerResetPasswordSchema(BaseModel):
    phone: str
    otp: str
    new_password: str = Field(min_length=6)


# =========================
# 🔑 CHANGE PASSWORD
# =========================
class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)
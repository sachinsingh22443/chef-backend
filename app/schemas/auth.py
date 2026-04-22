from pydantic import BaseModel, Field, EmailStr


# =========================
# 📱 CUSTOMER SIGNUP
# =========================
class CustomerSignupSchema(BaseModel):
    phone: str
    password: str = Field(min_length=6)
    otp: str


# =========================
# 🔐 CUSTOMER LOGIN
# =========================
class CustomerLoginSchema(BaseModel):
    phone: str
    password: str = Field(min_length=6)


# =========================
# 👨‍🍳 CHEF LOGIN (🔥 ADD THIS)
# =========================
class ChefLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


# =========================
# 🔐 FORGOT PASSWORD (OTP - CUSTOMER)
# =========================
class CustomerForgotPasswordSchema(BaseModel):
    phone: str


# =========================
# 🔑 RESET PASSWORD (OTP - CUSTOMER)
# =========================
class CustomerResetPasswordSchema(BaseModel):
    phone: str
    otp: str
    new_password: str = Field(min_length=6)


# =========================
# 🔑 CHANGE PASSWORD (COMMON)
# =========================
class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


# =========================
# 🔐 EMAIL BASED RESET (CHEF)
# =========================
class ForgotPasswordSchema(BaseModel):
    email: EmailStr


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str = Field(min_length=6)
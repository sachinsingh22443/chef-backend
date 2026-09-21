from pydantic import BaseModel, Field, EmailStr


# =========================
# 📱 CUSTOMER SIGNUP
# =========================

class CustomerSignupSchema(BaseModel):

    phone: str

    password: str = Field(min_length=6)

    otp: str

    # 🎁 OPTIONAL REFERRAL CODE
    referral_code: str | None = None


# =========================
# 🔐 CUSTOMER LOGIN
# =========================

class CustomerLoginSchema(BaseModel):

    phone: str

    password: str = Field(min_length=6)


# =========================
# 👨‍🍳 CHEF LOGIN
# =========================

class ChefLoginSchema(BaseModel):

    email: EmailStr

    password: str = Field(min_length=6)


# =========================
# 🔐 FORGOT PASSWORD
# CUSTOMER - OTP
# =========================

class CustomerForgotPasswordSchema(BaseModel):

    phone: str


# =========================
# 🔑 RESET PASSWORD
# CUSTOMER - OTP
# =========================

class CustomerResetPasswordSchema(BaseModel):

    phone: str

    otp: str

    new_password: str = Field(min_length=6)


# =========================
# 🔄 REFRESH TOKEN
# =========================

class RefreshTokenSchema(BaseModel):

    refresh_token: str


# =========================
# 🔑 CHANGE PASSWORD
# COMMON
# =========================

class ChangePasswordSchema(BaseModel):

    current_password: str

    new_password: str = Field(min_length=6)


# =========================
# 🔐 EMAIL BASED RESET
# CHEF
# =========================

class ForgotPasswordSchema(BaseModel):

    email: EmailStr


class ResetPasswordSchema(BaseModel):

    token: str

    new_password: str = Field(min_length=6)
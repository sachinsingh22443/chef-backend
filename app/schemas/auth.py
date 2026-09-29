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
    
    


class DeliveryPartnerSignupSchema(BaseModel):
    name: str = Field(..., min_length=2)
    email: str
    phone: str
    password: str = Field(..., min_length=6)

    date_of_birth: str | None = None

    address: str
    city: str
    state: str
    pincode: str

    vehicle_type: str
    vehicle_number: str

    driving_license_number: str
    driving_license_image: str | None = None

    id_proof_type: str
    id_proof_number: str
    id_proof_image: str | None = None

    account_holder_name: str
    account_number: str
    ifsc_code: str
from pydantic import BaseModel, EmailStr, Field


class BaseResponse(BaseModel):
    message: str
    
class CustomerSignupSchema(BaseModel):
    phone: str
    password: str = Field(min_length=4)
    otp: str


class CustomerLoginSchema(BaseModel):
    phone: str
    password: str


class CustomerForgotPasswordSchema(BaseModel):
    phone: str


class CustomerResetPasswordSchema(BaseModel):
    phone: str
    otp: str
    new_password: str = Field(min_length=4)
    
    
class ChefSignupSchema(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str = Field(min_length=4)

    address: str
    fssai_number: str

    account_holder_name: str
    account_number: str
    ifsc_code: str

    bio: str
    location: str
    specialties: str

    latitude: float | None = None
    longitude: float | None = None


class ChefLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)
    
    
class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str = Field(min_length=4)


class ForgotPasswordSchema(BaseModel):
    email: EmailStr


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str = Field(min_length=4)
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


class LoginResponse(TokenResponse):
    application_status: str | None = None
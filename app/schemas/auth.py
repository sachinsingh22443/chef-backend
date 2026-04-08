from pydantic import BaseModel
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None

class SignupSchema(BaseModel):
    name: str
    email: str
    phone: str
    password: str

    address: str
    fssai_number: str

    account_holder_name: str
    account_number: str
    ifsc_code: str
    
    bio: str 
    location: str 
    specialties: str 
    
from pydantic import BaseModel, EmailStr, Field

class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)
    
from pydantic import BaseModel

class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str
